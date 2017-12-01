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


class TensorplexClient(object):
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


def _wrap_method(fname, old_method):
    if test_bind_partial(old_method, _client_id_=0):
        def _method(self, *args, **kwargs):
            self.zmqueue.enqueue(
                (fname, self._client_id, args, kwargs)
            )
    else:
        def _method(self, *args, **kwargs):
            self.zmqueue.enqueue(
                (fname, None, args, kwargs)
            )
    return _method


delegate_methods(
    target_obj=TensorplexClient,
    src_obj=Tensorplex,
    wrapper=_wrap_method,
    doc_signature=False,
    exclude=Tensorplex._EXCLUDE_METHODS
)


Tensorplex.start_server = start_tensorplex_server


