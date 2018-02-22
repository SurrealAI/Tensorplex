import logging
import os
import inspect
from .logger import Logger
from .utils import mkdir, delegate_methods
from .local_proxy import LocalProxy


class Loggerplex(object):
    def __init__(self, folder,
                 overwrite=False,
                 level='info',
                 format=None,
                 time_format='hms',
                 show_level=True):
        self.log_files = {}
        self.folder = os.path.expanduser(folder)
        mkdir(self.folder)
        assert os.path.exists(self.folder), 'cannot create folder '+self.folder
        self._loggers = {}
        self._file_mode = 'w' if overwrite else 'a'
        self._log_level = level
        self._format = format
        self._time_format = time_format
        self._show_level = show_level

    def _get_client_logger(self, client_id):
        client_id = str(client_id)
        if client_id not in self._loggers:
            log_file = os.path.join(self.folder, client_id + '.log')
            self.log_files[client_id] = log_file
            _log = Logger.get_logger(
                client_id,
                level=self._log_level,
                file_name=log_file,
                file_mode=self._file_mode,
                format=self._format,
                time_format=self._time_format,
                show_level=self._show_level,
                stream=None,
                reset_handlers=True
            )
            self._loggers[client_id] = _log
        return self._loggers[client_id]

    def proxy(self, client_id):
        """
        Must be called AFTER registering all the groups!
        """
        return LocalProxy(self, client_id, exclude=[])


def _wrap_method(fname, old_method):
    def _method(self, *args, _client_id_, **kwargs):
        _log = self._get_client_logger(_client_id_)
        old_method(_log, *args, **kwargs)
    return _method


delegate_methods(
    target_obj=Loggerplex,
    src_obj=Logger,
    wrapper=_wrap_method,
    doc_signature=True,
    exclude=['configure', 'get_logger', 'wrap_logger',
             'remove_all_handlers', 'add_stream_handler', 'add_file_handler',
             'all_loggers', 'set_formatter', 'get_datefmt', 'exists'],
)
