from .utils import *
from .zmq_queue import *
from .local_loggerplex import Loggerplex
from .logger import Logger


def start_loggerplex_server(loggerplex, port):
    q = ZmqQueueServer(port=port, is_batched=True)
    while True:
        method_name, client_id, args, kwargs = q.dequeue()
        tplex_method = getattr(loggerplex, method_name)
        tplex_method(*args, _client_id_=client_id, **kwargs)


class LoggerplexClient(object):
    # avoid creating the Zmq socket over and over again
    _ZMQUEUE = {}

    def __init__(self, client_id, *, host, port,
                 enable_local_logger=False,
                 local_logger_stream='stdout',
                 local_logger_level=Logger.INFO,
                 local_logger_format=None,
                 local_logger_time_format=None):
        """
        Args:
            client_id: file name of the log file on remote server.
            host:
            port:
            enable_local_logger: print log to local stdout AND send to remote.
            local_logger_stream: "stdout" or "stderr"
            local_logger_level: Logger.DEBUG, Logger.INFO, etc.
            local_logger_format: see `Logger.configure`
            local_logger_time_format: see `Logger.configure`
        """
        self.zmqueue = self._get_client(host, port)
        self._client_id = client_id
        if enable_local_logger:
            self._local_logger = Logger.get_logger(
                'local_{}'.format(client_id),
                level=local_logger_level,
                file_name=None,
                file_mode=None,
                format=local_logger_format,
                time_format=local_logger_time_format,
                show_level=True,
                stream=local_logger_stream,
                reset_handlers=True
            )
        else:
            self._local_logger = None

    def exception(self, *args, exc, **kwargs):
        "stringify the traceback before sending over network"
        exc = Logger.exception2str(exc)
        self._exception(*args, exc=exc, **kwargs)

    def _get_client(self, host, port):
        if (host, port) in self._ZMQUEUE:
            return self._ZMQUEUE[host, port]
        zmqueue = ZmqQueueClient(
            host=host,
            port=port,
            flush_time=0.2,
        )
        self._ZMQUEUE[host, port] = zmqueue
        return zmqueue


def _method_wrapper(fname, old_method):
    # special case
    if fname == 'exception':
        def _method(self, *args, exc, **kwargs):
            assert isinstance(exc, Exception)
            exc = Logger.exception2str(exc)
            kwargs['exc'] = exc
            self.zmqueue.enqueue(
                ('exception', self._client_id, args, kwargs)
            )
            if self._local_logger:
                self._local_logger.exception(*args, **kwargs)
    else:
        def _method(self, *args, **kwargs):
            self.zmqueue.enqueue(
                (fname, self._client_id, args, kwargs)
            )
            if self._local_logger:
                getattr(self._local_logger, fname)(*args, **kwargs)
    return _method


delegate_methods(
    target_obj=LoggerplexClient,
    src_obj=Loggerplex,
    wrapper=_method_wrapper,
    doc_signature=False
)


Loggerplex.start_server = start_loggerplex_server

