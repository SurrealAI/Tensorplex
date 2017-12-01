import logging
import os
import inspect
from .logger import Logger
from .utils import mkdir
from .local_proxy import LocalProxy


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
            def _method(self, *args, _client_id_, _name_=mname, **kwargs):
                _log = self._get_client_logger(_client_id_)
                getattr(_log, _name_)(*args, **kwargs)
            _method.__doc__ = inspect.getdoc(getattr(Logger, mname))
            attrs[mname] = _method
        return super().__new__(cls, name, bases, attrs)


class Loggerplex(metaclass=_DelegateMethod):
    def __init__(self, folder, overwrite=False, debug=False):
        self.log_files = {}
        self.folder = os.path.expanduser(folder)
        mkdir(self.folder)
        assert os.path.exists(self.folder), 'cannot create folder '+self.folder
        self._loggers = {}
        self._file_mode = 'w' if overwrite else 'a'
        self._log_level = logging.DEBUG if debug else logging.INFO

    def _get_client_logger(self, client_id):
        if client_id not in self._loggers:
            log_file = os.path.join(self.folder, client_id + '.log')
            self.log_files[client_id] = log_file
            _log = Logger.get_logger(
                client_id,
                level=self._log_level,
                file_name=log_file,
                file_mode=self._file_mode,
                time_format='hms',
                show_level=True,
                reset_handlers=True
            )
            self._loggers[client_id] = _log
        return self._loggers[client_id]

    def proxy(self, client_id):
        """
        Must be called AFTER registering all the groups!
        """
        return LocalProxy(self, client_id, exclude_methods=[])

