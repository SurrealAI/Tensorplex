"""
DEPRECATED. Pyro4 mode is much, much slower than ZMQ mode.
For reference only.

Before running the server, first run `pyro4-ns -p 8008` in command line.
"""
import Pyro4
from .tensorplex import Tensorplex
from tensorplex.utils import iter_methods, test_bind_partial
import functools


# Pyro4.config.SERIALIZER = 'pickle'


# Add Pyro decorators
for _fname, _func in iter_methods(Tensorplex):
    setattr(Tensorplex, _fname, Pyro4.expose(Pyro4.oneway(_func)))


def start_tensorplex_server(tensorplex, port, ns_port):
    assert isinstance(tensorplex, Tensorplex)
    with Pyro4.Daemon(port=port) as daemon:
        tplex_uri = daemon.register(tensorplex)
        with Pyro4.locateNS(host='localhost', port=ns_port) as ns:
            ns.register('tensorplex', tplex_uri)
        daemon.requestLoop()


def is_pyro_exposed(func):
    return (hasattr(func, '_pyroExposed')
            and getattr(func, '_pyroExposed') is True)


class _DelegateMethod(type):
    """
    All methods called on LoggerplexServer will be delegated to self._log
    """
    def __new__(cls, name, bases, attrs):
        for fname, func in iter_methods(Tensorplex):
            if not is_pyro_exposed(func):
                continue
            # if the method accepts _client_id_
            if test_bind_partial(func, _client_id_=0):
                def _method(self, *args, _method_name_=fname, **kwargs):
                    return getattr(self._client, _method_name_)(
                        *args, _client_id_=self._client_id, **kwargs
                    )
            else:
                def _method(self, *args, _method_name_=fname, **kwargs):
                    return getattr(self._client, _method_name_)(
                        *args, **kwargs
                    )
            _method.__name__ = fname
            attrs[fname] = _method
        return super().__new__(cls, name, bases, attrs)


class TensorplexClient(metaclass=_DelegateMethod):
    # avoid creating proxy over and over again
    _CLIENTS = {}

    def __init__(self, *, client_id, host, port):
        self._client = self._get_client(host, port)
        self._client_id = client_id
        # for fname, func_class in iter_methods(Tensorplex):
        #     if not hasattr(self._client, fname):
        #         continue
        #     func_client = getattr(self._client, fname)
        #     print(fname, func_client)
        #     # if the method accepts _client_id_
        #     if test_bind_partial(func_class, _client_id_=client_id):
        #         setattr(self, fname,
        #                 functools.partial(func_client, _client_id_=client_id))
        #     else:
        #         setattr(self, fname, func_client)

    def _get_client(self, host, port):
        if (host, port) in self._CLIENTS:
            return self._CLIENTS[host, port]
        with Pyro4.locateNS(host=host, port=port) as ns:
            uri = ns.lookup('tensorplex')
            client = Pyro4.Proxy(uri)
        self._CLIENTS[host, port] = client
        return client

