
from . import docker_interface
from . import nginx_interface
from . import redis_interface
from . import types

from api_core import api_inspector
from api_core import hal


class ServerDB(hal.Storage[types.Server]):
  def __init__(self, redis_interface):
    super().__init__()
    self._redis = redis_interface
    
  def Lookup(self, key:str) -> types.Server:
    return self._redis.Get(key)

  def Enumerate(self) -> [types.Server]:
    return list(self._redis.GetAll())


def main():
  # Create the database that's used to store the server configs
  conn = redis_interface.RedisTypeInterface(types.Server)
  conn.Connect('localhost', 6379, None)

  # Set up the nginx interface - this will parse the existing
  # nginx config as well as install listeners to redis for changes
  nginx = nginx_interface.StartThread('/etc/nginx/nginx.conf', conn)

  # Set up the docker interface - this will check the current state
  # of docker, and then set up a thread that watches for changes
  docker = docker_interface.StartThread(conn)

  # Create the database object for the HAL service
  servers = ServerDB(conn)

  # Set the api path
  app = hal.Api('/api/v1')

  # Bind the ServerDB to /api/v1/servers
  app.add_resource(types.Server, servers, '/servers')

  # Attach the api browser
  api_inspector.InstallApiInspector(app)

  # Run the server
  app.run()

  # Join the threads
  docker.join()
  nginx.join()
  