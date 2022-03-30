
from api_core import hal


class Location(hal.HALStruct):
  ''' Represents an NGINX config `location` block nested within a
      a `server` block. 
  '''
  name: str
  types: str
  root: str
  expires: str
  proxy_pass: str
  fastcgi_pass: str
  autoindex: str


class Server(hal.HALEndpoint['hostname']):
  ''' Represents an NGINX config `server` block joined with a
      docker container informational dump
  '''
  hostname: str
  listen: int
  access_log: str
  root: str
  server_name: str
  locations: [Location]
  docker_status: str
  docker_container_id: str