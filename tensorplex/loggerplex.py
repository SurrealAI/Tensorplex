import logging
import os
import inspect
from .local_logger import Logger
from .remote_call import RemoteCall


class _DelegateMethod(type):
    """
    All methods called on LoggerplexServer will be delegated to self._log
    """
    def __new__(cls, name, bases, attrs):
        method_names = ['debug', 'info', 'warning', 'error',
                        'critical', 'exception', 'section']
        # custom info/debug levels
        method_names += ['debug'+str(i) for i in range(1, 10)]
        method_names += ['info'+str(i) for i in range(1, 10)]

        for mname in method_names:
            def _method(self, *args, __name=mname, **kwargs):
                getattr(self._log, __name)(*args, **kwargs)
            _method.__doc__ = inspect.getdoc(getattr(Logger, mname))
            attrs[mname] = _method
        return super().__new__(cls, name, bases, attrs)


class LoggerplexServer(metaclass=_DelegateMethod):
    def __init__(self, folder, overwrite=False, debug=False):
        self.log_files = {}
        self.folder = os.path.expanduser(folder)
        assert os.path.exists(self.folder), \
            'folder {} does not exist'.format(self.folder)
        self._loggers = {}
        self._log = None  # current logger
        self._file_mode = 'w' if overwrite else 'a'
        self._log_level = logging.DEBUG if debug else logging.INFO

    def _set_client_id(self, client_id):
        if client_id in self._loggers:
            self._log = self._loggers[client_id]
        else:
            log_file = os.path.join(self.folder, client_id + '.log')
            self.log_files[client_id] = log_file
            self._log = Logger.get_logger(
                client_id,
                level=self._log_level,
                file_name=log_file,
                file_mode=self._file_mode,
                time_format='hms',
                show_level=True,
                reset_handlers=True
            )
            self._loggers[client_id] = self._log

    def start_server(self, host, port):
        RemoteCall(
            self,
            host=host,
            port=port,
            queue_name=self.__class__.__name__,
            has_client_id=True,
            has_return_value=False
        ).run()


def _make_loggerplex_client():
    LoggerplexClient = RemoteCall.make_client_class(
        LoggerplexServer,
        new_cls_name='LoggerplexClient',
        has_return_value=False
    )
    _old_exception_method = LoggerplexClient.exception

    def _new_exception_method(self, *args, exc, **kwargs):
        "stringify the traceback before sending over network"
        exc = Logger.exception2str(exc)
        _old_exception_method(self, *args, exc=exc, **kwargs)

    LoggerplexClient.exception = _new_exception_method
    return LoggerplexClient


LoggerplexClient = _make_loggerplex_client()
