import inspect
import pickle
import sys

import redis

from tensorplex.utils import random_string


def _flag(call_hash):
    return 'flag:'+call_hash


_LUA_CHECK_FLAG = """
local flag_key = KEYS[1]
local future_queue = KEYS[2]
if redis.call('GET', flag_key) then
    return redis.call('LPUSH', future_queue, ARGV[1])
else
    return nil
end
"""


class RemoteFuture(object):
    def __init__(self, redis_client, call_hash):
        self._client = redis_client
        self._pipe = self._client.pipeline(transaction=False)
        self._call_hash = call_hash
        self._discarded = False

    def get(self, timeout=0):
        if self._discarded or self._client.get(_flag(self._call_hash)) is None:
            return None  # already deleted
        value = self._client.brpop(self._call_hash, timeout=timeout)
        if value is None:
            return None  # timeout
        else:
            _, value = value  # Redis-py: first return value is queue_name
            self.discard()
            return pickle.loads(value)

    def discard(self):
        # when deleted, remove the Redis reference as well
        self._pipe.delete(_flag(self._call_hash))
        self._pipe.delete(self._call_hash)
        # time.sleep(0.1)
        self._pipe.execute()
        self._discarded = True

    def __del__(self):
        self.discard()


class RemoteCall(object):
    def __init__(self,
                 local_object,
                 host,
                 port,
                 queue_name,
                 has_client_id,
                 has_return_value):
        self._client = redis.StrictRedis(host=host, port=port)
        self._pipe = self._client.pipeline(transaction=False)
        self._obj = local_object
        self._queue_name = queue_name
        self._methods = {}
        self._has_client_id = has_client_id
        self._has_return_value = has_return_value
        for fname in dir(self._obj):
            func = getattr(self._obj, fname)
            if callable(func) and not fname.startswith('_'):
                self._methods[fname] = func
        if self._has_client_id:
            assert (hasattr(self._obj, '_set_client_id')
                    and callable(getattr(self._obj, '_set_client_id'))), \
                'object must have the special method _set_client_id()'
        self._check_flag_push = self._client.register_script(_LUA_CHECK_FLAG)

    def run(self):
        """
        Assume the received data is (method_name, args, kwargs, call_hash)
        Dequeue from redis task queue
        """
        while True:
            _, binary = self._client.brpop(self._queue_name)
            (method_name,
             args,
             kwargs,
             client_id,
             call_hash) = pickle.loads(binary)
            if method_name not in self._methods:
                print(
                    'Method {}() does not exist.'.format(method_name),
                    file=sys.stderr
                )
                continue
            # execute the remote method TODO handle exception
            if self._has_client_id:
                self._obj._set_client_id(client_id)
            result = self._methods[method_name](*args, **kwargs)
            # check if we want to push the result
            if self._has_return_value:
                self._check_flag_push(
                    keys=[_flag(call_hash), call_hash],
                    args=[pickle.dumps(result)]
                )

    @staticmethod
    def make_client_class(cls,
                          new_cls_name,
                          has_return_value,
                          exclude_methods=None):
        """
        Args:
            cls:
            new_cls_name:
            has_return_value:
            exclude_methods: list of instance methods to be excluded in the
                proxy API if None, include all non-private methods from server
        """
        assert inspect.isclass(cls)
        methods = {}
        if exclude_methods is None:
            exclude_methods = []

        def __init__(self,
                     client_id,
                     host,
                     port,
                     queue_name=cls.__name__):
            self._client_id = client_id
            self._client = redis.StrictRedis(host=host, port=port)
            self._pipe = self._client.pipeline(transaction=False)
            self._queue_name = queue_name

        methods['__init__'] = __init__

        for fname in dir(cls):
            func = getattr(cls, fname)
            if (callable(func) and
                    not fname.startswith('_') and
                    not fname in exclude_methods):
                # hijacks the function to be a redis call
                old_sig = inspect.signature(func)

                def _new_method(self, *args,
                                __old_sig=old_sig,
                                __fname=fname,
                                **kwargs):
                    __old_sig.bind(self, *args, **kwargs)  # check signature
                    call_hash = random_string()
                    data = (__fname, args, kwargs, self._client_id, call_hash)
                    if has_return_value:
                        self._pipe.set(_flag(call_hash), '1')
                    self._pipe.lpush(self._queue_name, pickle.dumps(data))
                    self._pipe.execute()
                    if has_return_value:
                        return RemoteFuture(self._client, call_hash)

                _new_method.__doc__ = inspect.getdoc(func)  # preserve docstring
                methods[fname] = _new_method

        return type(new_cls_name, (), methods)

