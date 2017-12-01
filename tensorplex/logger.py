import os
import sys
import io
import traceback
import logging
import inspect


def _get_level_names():
    names = {}
    for i in range(1, 10):
        names[logging.DEBUG + i] = 'DEBUG'+str(i)
        names[logging.INFO + i] = 'INFO'+str(i)
    # add to standard lib
    for level, name in names.items():
        setattr(logging, name, level)
    return names


_LEVEL_NAMES = _get_level_names()


_LEVEL_NAMES.update({
    logging.CRITICAL : 'CRITICAL',
    logging.ERROR : 'ERROR',
    logging.WARNING : 'WARNING',
    logging.INFO : 'INFO',
    logging.DEBUG : 'DEBUG',
})


def log_level_name(level):
    return _LEVEL_NAMES.get(level, 'Level {}'.format(level))


# hack stdlib function to enable better printing
logging.getLevelName = log_level_name


# http://stackoverflow.com/questions/12980512/custom-logger-class-and-correct-line-number-function-name-in-log
# From python 3.5 source code:
# _srcfile is used when walking the stack to check when we've got the first
# caller stack frame, by skipping frames whose filename is that of this
# module's source. It therefore should contain the filename of this module's
# source file.
# Ordinarily we would use __file__ for this, but frozen modules don't always
# have __file__ set, for some reason (see Issue #21736). Thus, we get the
# filename from a handy code object from a function defined in this module.
# (There's no particular reason for picking log_level_name.)
#
_srcfile = os.path.normcase(log_level_name.__code__.co_filename)


def _expand_args(arg1, arg2):
    "Helper for add_file_handler and add_stream_handler"
    if not isinstance(arg1, list):
        arg1 = [arg1]
    if not isinstance(arg2, list):
        arg2 = [arg2]
    if len(arg1) == 1:
        # extend to the same length list as arg2
        arg1 = arg1 * len(arg2)
    if len(arg2) == 1:
        arg2 = arg2 * len(arg1)
    assert len(arg1) == len(arg2), \
        '{} and {} size mismatch'.format(arg1, arg2)
    return zip(arg1, arg2)


def _expand_arg(arg):
    "expand an arg into a singleton list"
    if isinstance(arg, list):
        return arg
    else:
        return [arg]


def _process_msg(*args, **kwargs):
    # if 'sep' is provided, we will use the custom separator instead
    sep = kwargs.pop('sep', ' ')
    # e.g. "{}, {}, {}" if sep = ", "
    msg = sep.join([u'{}'] * len(args)).format(*args)
    return msg, kwargs


def _process_msg_fmt(msg, *args, **kwargs):
    fmt_kwargs = {}
    for key, value in kwargs.copy().items():
        if not key in ['exc_info', 'stack_info', 'extra']:
            fmt_kwargs[key] = value
            # must remove unsupported keyword for internal args
            kwargs.pop(key)
    msg = msg.format(*args, **fmt_kwargs)
    return msg, kwargs


class _NewFormatMeta(type):
    def __new__(cls, cls_name, bases, attrs):
        # generate standard methods like logger.warning(...)
        def _gen_std_levels(name, is_fmt):
            if is_fmt:
                _process = _process_msg_fmt
            else:
                _process = _process_msg

            def _method(self, *args, **kwargs):
                # e.g. logging.DEBUG
                level = getattr(logging, name.upper())
                if self.logger.isEnabledFor(level):
                    msg, kwargs = _process(*args, **kwargs)
                    self._log(level, msg, **kwargs)

            _method.__doc__ = inspect.getdoc(getattr(logging.Logger, name))
            return _method

        def _gen_section(name):
            def _method(self, *msg, sep='=', repeat=20, **kwargs):
                # e.g. logging.DEBUG
                level = getattr(logging, name.upper())
                self.section(*msg,
                             level=level, sep=sep, repeat=repeat, **kwargs)
            _method.__doc__ = inspect.getdoc(getattr(logging.Logger, name))
            return _method

        for name in ['debug', 'info', 'warning', 'error', 'critical']:
            attrs[name] = _gen_std_levels(name, False)
            attrs[name+'fmt'] = _gen_std_levels(name, True)
            attrs[name+'section'] = _gen_section(name)

        # generate logger.info3(...) and logger.debug8(...)
        def _gen_custom_levels(level, is_fmt):
            def _method(self, msg, *args, **kwargs):
                if is_fmt:
                    return self.logfmt(level, msg, *args, **kwargs)
                else:
                    return self.log(level, msg, *args, **kwargs)
            _method.__doc__ = "custom logging level "+str(level)
            return _method

        for level in range(1, 10):
            attrs['info{}'.format(level)] = \
                _gen_custom_levels(logging.INFO + level, False)
            attrs['info{}fmt'.format(level)] = \
                _gen_custom_levels(logging.INFO + level, True)
            attrs['debug{}'.format(level)] = \
                _gen_custom_levels(logging.DEBUG + level, False)
            attrs['debug{}fmt'.format(level)] = \
                _gen_custom_levels(logging.DEBUG + level, True)

        for level, name in _LEVEL_NAMES.items():
            attrs[name] = level
        return super().__new__(cls, cls_name, bases, attrs)
        

class Logger(metaclass=_NewFormatMeta):
    """
    logger = Logger(logger)
    fully supports positional/keyword new formatter string syntax

    Example:
    
    ::
        logger.info("Float {1:>7.3f} and int {0} with {banana} and {apple:.6f}", 
                    66, 3.141592, apple=7**.5, banana='str')
        # if the first arg isn't a format string, treat as if print statement
        # you can specify a `sep=` arg under this case. `sep` defaults to space
        logger.info({3:'apple', 4:'banana'}, 4.5, 'asdf')
        logger.info('I am not a format string', 66, {'key':'value'}, sep=', ')
    
    Custom verbosity level. The higher the more strings printed. 
    log.info1(), .info2() ... info5(). 
    corresponding levels: INFO1 to INFO5
    """
    # https://docs.python.org/3/library/logging.html#logrecord-attributes
    """
    Example: 
    
    # print out all format attributes
    fmt_string = ''
    for s in LoggerPro.FORMAT_ATTRS:
        fmt_string += '{0}={{{0}}}\n'.format(s)
    print(fmt_string)
    log.set_formatter((fmt_string, None))
    log.info('HELLO', 'WORLD!')
    """
    FORMAT_ATTRS = ['pathname', 'filename', 'lineno', 'funcName', 'module',
                  'process', 'processName', 'thread', 'threadName',
                  'created', 'relativeCreated', 'msecs',
                  'levelname', 'levelno', 'asctime', 'message']
    
    def __init__(self, logger):
        self.logger = logger
        
    def __getattr__(self, attr):
        "Access wrapped logger methods transparently"
        if attr in dir(self):
            return object.__getattribute__(self, attr)
        else:
            return getattr(self.logger, attr)

    @staticmethod
    def exception2str(exc):
        buf = io.StringIO()
        traceback.print_exception(
            type(exc),
            exc,
            exc.__traceback__,
            file=buf
        )
        buf = buf.getvalue().strip()
        return '\n'.join(['ERROR> ' + line for line in buf.split('\n')])

    def exception(self, msg, *args, exc, **kwargs):
        """
        Logs a message with level ERROR on this logger. 
        Exception info is always added to the logging message. 

        Args:
            exc: the exception value that extends BaseException

        Warning:
            Only Python3 supports exception.__traceback__
        """
        if self.logger.isEnabledFor(logging.ERROR):
            msg, kwargs = _process_msg(msg, *args, **kwargs)
            msg += '\n'
            if isinstance(exc, str):  # see LoggerplexClient
                msg += exc
            else:
                msg += self.exception2str(exc)
            self.logger.error(msg, **kwargs)
    
    def log(self, level, msg, *args, **kwargs):
        """
        Log with user-defined level, e.g. INFO_V0 to INFO_V5
        """
        if self.logger.isEnabledFor(level):
            msg, kwargs = _process_msg(msg, *args, **kwargs)
            # self.logger.log(level, msg, **kwargs)
            self._log(level, msg, **kwargs)

    def logfmt(self, level, msg, *args, **kwargs):
        """
        Log with user-defined level, e.g. INFO_V0 to INFO_V5
        """
        if self.logger.isEnabledFor(level):
            msg, kwargs = _process_msg_fmt(msg, *args, **kwargs)
            # self.logger.log(level, msg, **kwargs)
            self._log(level, msg, **kwargs)

    def section(self, *msg, level=logging.INFO, sep='=', repeat=20, **kwargs):
        """
        Display a section segment line

        Args:
          msg: to be displayed in the middle of the sep line
              can have str.format *args and **kwargs just like the other methods
          level: defaults to INFO
          sep: symbol to be repeated for a long segment line
          repeat: 'sep' * repeat, the length of segment string
        
        Example:
          logger.section(sep='!', repeat=80) # long unbroken line of '!'
          logger.section('My message about {} and {x}', 100, x=200, level=logging.DEBUG)
        """
        if self.logger.isEnabledFor(level):
            if len(msg) == 0: # no vararg
                msg = ''
                args = tuple()
            else:
                msg, *args = msg
            msg, _ = _process_msg(msg, *args, **kwargs)
            msg = u'{sep}{space}{msg}{space}{sep}'.format(
                sep=sep*(repeat//2),
                msg=msg,
                space=' ' if msg else ''
            )
            self._log(level, msg)

    def remove_all_handlers(self):
        for handle in self.logger.handlers:
            self.logger.removeHandler(handle)

    def configure(self,
                  level=None, 
                  file_name=None,
                  file_mode='a',
                  format=None,
                  time_format=None,
                  show_level=False,
                  stream=None,
                  reset_handlers=False):
        """
        Args:
          level: None to retain the original level of the logger
          file_name: None to print to console only
          file_mode: 'w' to override a file or 'a' to append
          format: `{}` style logging format string, right after level name
          time_format:
            - `dhms`: %m/%d %H:%M:%S
            - `dhm`: %m/%d %H:%M
            - `hms`: %H:%M:%S
            - `hm`: %H:%M
            - if contains '%', will be interpreted as a time format string
            - None
          show_level: if True, display `INFO> ` before the message
          stream: 
            - stream object: defaults to sys.stderr
            - str: "out", "stdout", "err", or "stderr"
            - None: do not print to any stream
          reset_handlers: True to remove all old handlers

        Notes:
            log format rules:
            levelname> [format] ...your message...

            If show_level is True, `levelname> ` will be the first
            If format is None and time_format is None, nothing prints
            If format is None and time_format specified, print time
            If format specified, time_format will take effect only if
                '{asctime}' is contained in the format.
            E.g. if format is empty string, nothing will print even if
            time_format is set.

        References:
        - for format string:
            https://docs.python.org/3/library/logging.html#logrecord-attributes
        - for time_format string:
            https://docs.python.org/3/library/time.html#time.strftime

        Warning:
          always removes all previous handlers
        """
        if reset_handlers:
            self.remove_all_handlers()
        if level:
            if isinstance(level, str):  # "INFO", "WARNING"
                level = level.upper()
                level = getattr(self, level)
            self.logger.setLevel(level)
        self.add_stream_handler(stream, format, time_format, show_level)
        self.add_file_handler(file_name, file_mode,
                              format, time_format, show_level)
        return self
    
    @classmethod
    def get_logger(cls, name, *args, **kwargs):
        """
        Returns:
          a logger with the same config args as `.configure(...)`
          - if the logger already exists, retain its previous level
          - if new logger, set to INFO as default level

        Note:
          set `propagate` to False to prevent double-printing
          https://stackoverflow.com/questions/11820338/replace-default-handler-of-python-logger
        """
        if not Logger.exists(name) and 'level' not in kwargs:
            kwargs['level'] = logging.INFO
        raw_logger = logging.getLogger(name)
        raw_logger.propagate = False
        return cls(raw_logger).configure(*args, **kwargs)
    
    @classmethod
    def wrap_logger(cls, logger):
        """
        Args:
          logger: if string, logging.getLogger(). Else wrap and return.
        """
        if isinstance(logger, str):
            logger = logging.getLogger(logger)
        return cls(logger)

    def _get_formatter(self, format, time_format, show_level):
        levelname = '{levelname}> ' if show_level else ''
        if format is None:
            if time_format is not None:
                fmt = '{asctime} '
            else:
                fmt = ''
        else:
            fmt = format
        return logging.Formatter(
            fmt=fmt + levelname + '{message}',
            datefmt=self.get_datefmt(time_format),
            style='{'
        )
    
    def add_file_handler(self,
                         file_name,
                         file_mode='a',
                         format=None,
                         time_format=None,
                         show_level=False):
        """
        Args:
            file_name: one string or a list of strings
            file_mode: one mode or a list of modes, must match len(file_name)
        """
        if not file_name:
            return
        file_name = os.path.expanduser(file_name)
        formatter = self._get_formatter(format, time_format, show_level)
        for name, mode in _expand_args(file_name, file_mode):
            handler = logging.FileHandler(name, mode)
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        return self

    def add_stream_handler(self,
                           stream,
                           format=None,
                           time_format=None,
                           show_level=False):
        """
        Args:
            stream: 
            - stream object: e.g. sys.stderr
            - str: "out", "stdout", "err", or "stderr"
            - a list of the above to add multiple strings
        """
        if not stream:
            return
        formatter = self._get_formatter(format, time_format, show_level)
        for stream in _expand_arg(stream):
            if isinstance(stream, str):
                if stream in ['out', 'stdout']:
                    stream = sys.stdout
                elif stream in ['err', 'stderr']:
                    stream = sys.stderr
                else:
                    raise ValueError('Unsupported stream name: '+stream)
            handler = logging.StreamHandler(stream)
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        return self
    
    def get_datefmt(self, time_format):
        """
        Alias for common date formats
        """
        return {'yd': '%m-%d-%y',
                'ydhm': '%m-%d-%y %H:%M',
                'ydhms': '%m-%d-%y %H:%M:%S',
                'dhm': '%m-%d %H:%M',
                'dhms':'%m-%d %H:%M:%S', 
                'hms': '%H:%M:%S', 
                'hm': '%H:%M'}.get(time_format, time_format)

    def set_formatter(self, formatter):
        """
        Sets a custom formatter for *all* handlers.
        https://docs.python.org/3/library/logging.html#formatter-objects

        Args:
          formatter: can be either of the following:
          - instance of logging.Formatter
          - fmt string, note that the style is `{}`
          - tuple of fmt strings (fmt, datefmt), note that the style is `{}`
        
        References:
        - for fmt string:
            https://docs.python.org/3/library/logging.html#logrecord-attributes
        - for datefmt string:
            https://docs.python.org/3/library/time.html#time.strftime
        """
        if isinstance(formatter, str):
            formatter = logging.Formatter(formatter, datefmt=None, style='{')
        elif isinstance(formatter, (list, tuple)):
            assert len(formatter) == 2, 'formatter=(fmt, datefmt) strings'
            fmt, datefmt = formatter
            datefmt = self.get_datefmt(datefmt)
            formatter = logging.Formatter(fmt, datefmt, style='{')
        elif not isinstance(formatter, logging.Formatter):
            raise TypeError('formatter must be either an instance of '
                    'logging.Formatter or a tuple of (fmt, datefmt) strings')
        for handler in self.logger.handlers:
            handler.setFormatter(formatter)

    @staticmethod
    def all_loggers():
        """
        http://stackoverflow.com/questions/13870555/how-to-clear-reset-all-configured-logging-handlers-in-python
        
        Returns: 
            a dict of all registered loggers under root
        """
        return logging.Logger.manager.loggerDict
    
    @staticmethod
    def exists(name):
        """
        Check whether a logger exists
        """
        return name in Logger.all_loggers()

    # ================================================
    # copy stdlib logging source code here to ensure that line numbers
    # and file locations are correct in the log message
    # http://stackoverflow.com/questions/12980512/custom-logger-class-and-correct-line-number-function-name-in-log
    # ================================================
    def _findCaller(self, stack_info=False):
        # Find the stack frame of the caller so that we can note the source
        # file name, line number and function name.
        f = logging.currentframe()
        #On some versions of IronPython, currentframe() returns None if
        #IronPython isn't run with -X:Frames.
        if f is not None:
            f = f.f_back
        rv = "(unknown file)", 0, "(unknown function)", None
        while hasattr(f, "f_code"):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)
            if filename == _srcfile:
                f = f.f_back
                continue
            sinfo = None
            if stack_info:
                sio = io.StringIO()
                sio.write('Stack (most recent call last):\n')
                traceback.print_stack(f, file=sio)
                sinfo = sio.getvalue()
                if sinfo[-1] == '\n':
                    sinfo = sinfo[:-1]
                sio.close()
            rv = (co.co_filename, f.f_lineno, co.co_name, sinfo)
            break
        return rv

    def _log(self, level, msg, args=tuple(), exc_info=None, extra=None, stack_info=False):
        # Low-level logging routine which creates a LogRecord and then calls
        # all the handlers of this logger to handle the record.
        sinfo = None
        if _srcfile:
            #IronPython doesn't track Python frames, so findCaller raises an
            #exception on some versions of IronPython. We trap it here so that
            #IronPython can use logging.
            try:
                fn, lno, func, sinfo = self._findCaller(stack_info)
            except ValueError: # pragma: no cover
                fn, lno, func = "(unknown file)", 0, "(unknown function)"
        else: # pragma: no cover
            fn, lno, func = "(unknown file)", 0, "(unknown function)"
        if exc_info:
            if isinstance(exc_info, BaseException):
                exc_info = (type(exc_info), exc_info, exc_info.__traceback__)
            elif not isinstance(exc_info, tuple):
                exc_info = sys.exc_info()
        record = self.logger.makeRecord(self.logger.name, level, fn, lno, msg, args,
                                        exc_info, func, extra, sinfo)
        self.logger.handle(record)
