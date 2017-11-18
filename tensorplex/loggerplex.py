import logging
import os
from .local_logger import Logger
from .remote_call import RemoteCall


class _DelegateLogMethod(type):
    """
    All methods called on Loggerplex will be delegated to self._log
    """
    def __new__(cls, name, bases, attrs):
        for name in ['debug',
                     'info',
                     'warning',
                     'error',
                     'critical',
                     'exception',
                     'section']:
            def _method(self, *args, __name=name, **kwargs):
                getattr(self._log, __name)(*args, **kwargs)
            attrs[name] = _method
        return super().__new__(cls, name, bases, attrs)


class Loggerplex(metaclass=_DelegateLogMethod):
    def __init__(self, folder):
        self.log_files = {}
        self._folder = folder
        self._loggers = {}
        self._log = None  # current logger

    def _set_client_id(self, client_id):
        if client_id in self._loggers:
            self._log = self._loggers[client_id]
        else:
            log_file = os.path.join(self._folder, client_id + '.log')
            self.log_files[client_id] = log_file
            self._log = Logger.get_logger(
                client_id,
                level=logging.INFO,
                file_name=log_file,
                file_mode='a',
                time_format='hms',
                show_level=True,
                reset_handlers=True
            )
            self._loggers[client_id] = self._log


LoggerplexClient = RemoteCall.make_client_class(
    Loggerplex,
    has_return_value=False
)
