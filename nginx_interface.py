
import collections
import dataclasses
import multiprocessing
import os
import threading

from . import types
from . import redis_interface
from nginx import nginxio


@dataclasses.dataclass
class ConfigUtil():
  filename: str
  config: nginxio.NginXConfig
  servers: {str:(types.Server, nginxio.NginXServer)}


def GenerateConfigUtil(file:str, config:nginxio.NginXConfig) -> ConfigUtil:
  servers = collections.OrderedDict()
  for n_server in config.http.servers:
    server = ConvertServer(n_server)
    servers[server.hostname] = (server, n_server)
  return ConfigUtil(file, config, servers)


def ThreadLoop(redis, config, changequeue):
  while True:
    try:
      u_type, u_value = changequeue.get(timeout=3600)
      if u_type == 'set':
        if AppendToConfig(config, u_value):
          with open(config.filename, 'w') as f:
            f.write(str(config.config))
          os.system('systemctl reload nginx.service')
      elif u_type == 'delete':
        if RemoveFromConfig(config, u_value):
          with open(config.filename, 'w') as f:
            f.write(str(config.config))
          os.system('systemctl reload nginx.service')
      elif u_type == 'shutdown':
        break
      else:
        raise ValueError(u_type)
    except Exception as e:
      print(e)


def RemoveFromConfig(cu: ConfigUtil, server:types.Server):
  old_server = cu.servers.get(server.hostname, None)
  if not old_server:
    return False
  del cu.servers[server.hostname]
  cu.config.http.servers = [ns for _,ns in cu.servers.values()]
  return True


def AppendToConfig(cu: ConfigUtil, server:types.Server):
  old_server = cu.servers.get(server.hostname, None)
  if old_server == server:
    return False
  n_server = nginxio.NginXServer.FromString(RecreateServer(server))
  if not old_server:
    cu.servers[server.hostname] = (server, n_server)
    cu.config.http.servers.append(n_server)
  else:
    cu.servers[server.hostname] = (server, n_server)
    cu.config.http.servers = [ns for _,ns in cu.servers.values()]
  return True


def RecreateLocation(location:types.Location) -> str:
  config = f'location {location.name} {{\n'
  for name in types.Location.__annotations__:
    if name == 'name':
      continue
    if value := getattr(location, name):
      config += f'  {name} {value};\n'
  config += '}'
  return config


def RecreateServer(server:types.Server) -> str:
  config = ''
  for name in types.Server.__annotations__:
    if name.startswith('docker'):
      continue
    if name == 'hostname':
      continue
    if value := getattr(server, name):
      if name == 'locations':
        for location in value:
          config += RecreateLocation(location)
          config += '\n'
      else:
        config += f'{name} {value};\n'
  return config


def ConvertLocation(location:nginxio.NginXLocation) -> types.Location:
  datapack = {'name': location.location}
  for prop in location.tags:
    if prop.name in types.Location.__annotations__:
      datapack[prop.name] = prop.value
  for name, typ in types.Location.__annotations__.items():
    if name not in datapack:
      datapack[name] = ''
  return types.Location(**datapack)


def ConvertServer(server:nginxio.NginXServer) -> types.Server:
  datapack = {}
  for prop in server.tags:
    if prop.name in types.Server.__annotations__:
      datapack[prop.name] = prop.value
  datapack['hostname'] = datapack['server_name'].split(' ')[0]
  datapack['locations'] = []
  for location in server.locations:
    datapack['locations'].append(ConvertLocation(location))
  for name, typ in types.Server.__annotations__.items():
    if name not in datapack:
      datapack[name] = ''
  return types.Server(**datapack)


def StartThread(file:str, redis:redis_interface.RedisTypeInterface):
  config = nginxio.NginXConfig.FromFile(file)
  for n_server in config.http.servers:
    server = ConvertServer(n_server)
    redis.Set(server.hostname, server)

  changequeue = multiprocessing.Queue()
  redis.InstallChangeNotifier(lambda x:changequeue.put(x))
  config = GenerateConfigUtil(file, config)
  t = threading.Thread(target=ThreadLoop, args=(redis, config, changequeue))
  t.start()
  return t