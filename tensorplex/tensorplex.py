from .utils import *
from .zmq_queue import *
from .local_tensorplex import Tensorplex


def start_tensorplex_server(tensorplex, port):
    q = ZmqQueueServer(port=port, is_batched=True)
    while True:
        method_name, client_id, args, kwargs = q.dequeue()
        tplex_method = getattr(tensorplex, method_name)
        if client_id is None:
            tplex_method(*args, **kwargs)
        else:
            tplex_method(*args, _client_id_=client_id, **kwargs)


class _DelegateMethod(type):
    """
    All methods called on LoggerplexServer will be delegated to self._log
    """
    def __new__(cls, name, bases, attrs):
        for fname, func in iter_methods(Tensorplex):
            # if the method accepts _client_id_
            if test_bind_partial(func, _client_id_=0):
                def _method(self, *args, _method_name_=fname, **kwargs):
                    self.zmqueue.enqueue(
                        (_method_name_, self._client_id, args, kwargs)
                    )
            else:
                def _method(self, *args, _method_name_=fname, **kwargs):
                    self.zmqueue.enqueue(
                        (_method_name_, None, args, kwargs)
                    )
            _method.__name__ = fname
            attrs[fname] = _method
        return super().__new__(cls, name, bases, attrs)


class TensorplexClient(metaclass=_DelegateMethod):
    # avoid creating the Zmq socket over and over again
    _ZMQUEUE = {}

    def __init__(self, *, client_id, host, port):
        self.zmqueue = self._get_client(host, port)
        self._client_id = client_id

    def _get_client(self, host, port):
        if (host, port) in self._ZMQUEUE:
            return self._ZMQUEUE[host, port]
        zmqueue = ZmqQueueClient(
            host=host,
            port=port,
            batch_interval=0.2,
        )
        self._ZMQUEUE[host, port] = zmqueue
        return zmqueue


Tensorplex.start_server = start_tensorplex_server


