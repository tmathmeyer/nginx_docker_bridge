
import dataclasses
import json
import subprocess
import threading

from . import types


@dataclasses.dataclass
class Container():
  container_id: str
  status: str
  ports: {str:int}
  hostname: str


def QueryRunningDockerContainers(flter):
  proc = subprocess.Popen([
    'docker', 'container', 'ls', '--no-trunc', '-f', flter,
    '--format', '{{.Ports}}\t{{.ID}}\t{{.Status}}\t{{.Image}}'],
    stdout=subprocess.PIPE, close_fds=True)
  for line in proc.communicate()[0].decode('utf-8').split('\n'):
    line = line.strip()
    if not line:
      continue
    ports, c_id, status, image = line.split('\t')
    hostname = GetDockerHostname(GetDockerImageInfo(image))
    portbindings = {}
    for binding in ports.split(','):
      ipport = binding.strip().split('->')[0].strip().rsplit(':', 1)
      if len(ipport) == 2:
        ip, port = ipport
        portbindings[ip.strip()] = int(port.strip())
    yield Container(c_id, status, portbindings, hostname)


def GetDockerImageInfo(image:str):
  proc = subprocess.Popen([
    'docker', 'image', 'inspect', image],
    stdout=subprocess.PIPE, close_fds=True)
  return json.loads(proc.communicate()[0].decode('utf-8'))[0]


def GetDockerHostname(imageinfo):
  cc = imageinfo.get('ContainerConfig', None)
  if not cc:
    return None
  labels = cc.get('Labels', None)
  if not labels:
    return None
  return labels.get('hostname', None)


def LinkContainersForFilter(redis, fltr):
  for container in QueryRunningDockerContainers(fltr):
    port = container.ports['0.0.0.0']
    host = 'localhost'
    if nginx := redis.Get(container.hostname):
      nginx.docker_container_status = container.status
      nginx.docker_container_id = container.container_id
      if len(nginx.locations) != 1:
        continue
      if nginx.locations[0]['proxy_pass'] == '':
        continue
      nginx.locations = [types.Location(**nginx.locations[0])]
      nginx.locations[0].proxy_pass = f'http://{host}:{port}'
      redis.SetDirect(container.container_id, container.hostname)
      redis.Set(container.hostname, nginx)
    else:
      new_server = types.Server(
        hostname=container.hostname,
        listen='80',
        access_log='',
        root='',
        server_name=container.hostname,
        docker_status=container.status,
        docker_container_id=container.container_id,
        locations=[types.Location(name='/', types='', root='', expires='',
                                 fastcgi_pass='', autoindex='',
                                 proxy_pass=f'http://{host}:{port}')])
      redis.SetDirect(container.container_id, container.hostname)
      redis.Set(container.hostname, new_server)


def DockerEventlistener(redis):
  proc = subprocess.Popen(
    ['docker', 'events', '--format', '{{json .}}'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    close_fds=True)
  for stdout_line in iter(proc.stdout.readline, ""):
    event = json.loads(stdout_line.decode('utf-8'))
    if event.get('status', None) == 'start':
      LinkContainersForFilter(redis, f'id={event["id"]}')
    elif event.get('status', None) == 'stop':
      docker_id = event.get('id')
      hostname = redis.GetDirect(docker_id).decode('utf-8')
      redis.DeleteDirect(docker_id)
      server = redis.Get(hostname)
      redis.Delete(hostname)


def StartThread(redis):
  LinkContainersForFilter(redis, 'status=running')
  thread = threading.Thread(target=DockerEventlistener, args=(redis,))
  thread.start()
  return thread