langs("Python")
load("//rules/env/Docker/build_defs.py")

py_binary (
  name = "nginx_docker_bridge",
  srcs = [
    "nginx_docker_bridge.py",
    "docker_interface.py",
    "nginx_interface.py",
    "redis_interface.py",
    "types.py",
  ],
  deps = [
    "//api_core:hal",
    "//api_core:api_inspector",
    "//nginx:nginxio",
  ],
  pips = [
    "redis",
  ],
)

py_binary (
  name = "demo_server",
  srcs = [ "demo_server.py", ],
  pips = [ "Flask", ],
)

container (
  name = "demo_service",
  main_executable = "demo_server",
  deps = [
    ":demo_server",
  ],
  binaries = [],
  docker_args = {
    "pip_packages": [],
    "alpine_packages": [],
    "environment": [],
    "ports": [5000],
    "args": ["hostname=demo.example.com"],
  }
)