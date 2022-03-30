
import json
import redis
import threading

class RedisTypeInterface():
  def __init__(self, typedecl:type):
    self._typedecl = typedecl
    self._typename = f'{typedecl.__name__}_keys'
    self._redis = None
    self._change_notifiers = {}
    self._change_notifiers_incr = 0
    self._lock = threading.Lock()

  def __del__(self):
    for handler in self._change_notifiers:
      handler(('shutdown', None))

  def _ensure_connected(self):
    class locker():
      def __enter__(_):
        if self._redis is None:
          raise ValueError('Redis Disconnected')
        self._lock.acquire()
        return self._redis
      def __exit__(*_):
        self._lock.release()
    return locker()

  def InstallChangeNotifier(self, fn):
    self._change_notifiers_incr += 1
    self._change_notifiers[self._change_notifiers_incr] = fn
    return self._change_notifiers_incr

  def UninstallChangeNotifier(self, h_id):
    del self._change_notifiers[h_id]

  def Connect(self, host, port, password):
    self._redis = redis.Redis(host, port, password)

  def Set(self, key:str, inst:'self._typedecl'):
    with self._ensure_connected() as redis:
      redis.set(key, json.dumps(inst.json()))
      keys = redis.get(self._typename)
      if not keys:
        keys = [key]
      else:
        keys = json.loads(keys)
        keys.append(key)
      redis.set(self._typename, json.dumps(keys))
      for handler in self._change_notifiers.values():
        handler(('set', inst))

  def Get(self, key:str) -> 'self._typedecl':
    with self._ensure_connected() as redis:
      if query := redis.get(key):
        return self._typedecl(**json.loads(query))
      return None

  def Delete(self, key):
    with self._ensure_connected() as redis:
      keys = json.loads(redis.get(self._typename))
      delkeys = list(filter((lambda k: k!=key), keys))
      if len(keys) != len(delkeys):
        inst = self._typedecl(**json.loads(redis.get(key)))
        redis.delete(key)
        redis.set(self._typename, json.dumps(delkeys))
        for handler in self._change_notifiers.values():
          handler(('delete', inst))

  def GetAll(self):
    with self._ensure_connected() as redis:
      keys = json.loads(redis.get(self._typename) or '[]')
      for key in keys:
        yield self._typedecl(**json.loads(redis.get(key)))

  def SetDirect(self, key:str, value:str):
    with self._ensure_connected() as redis:
      redis.set(key, value)

  def GetDirect(self, key:str):
    with self._ensure_connected() as redis:
      return redis.get(key)

  def DeleteDirect(self, key:str):
    with self._ensure_connected() as redis:
      return redis.delete(key)
