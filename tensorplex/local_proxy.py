import inspect
import multiprocessing

from tensorplex.utils import iter_methods, test_bind_partial


class LocalProxy(object):
    """
    Usage: in your server class, add the following method:

    def get_proxy(self, client_id):
        return LocalProxy(self, client_id, exclude_methods=[...])
    """
    LOCK_ATTR = '_internal_proxy_lock_'

    def __init__(self, instance, client_id, exclude_methods=None):
        self._instance = instance
        # _instance.LOCK_ATTR is a singleton
        if hasattr(instance, self.LOCK_ATTR):  # DEPRECATED
            _proxy_lock = getattr(instance, self.LOCK_ATTR)
            # protect against both thread and process
            assert isinstance(_proxy_lock, type(multiprocessing.Lock()))
        else:
            _proxy_lock = multiprocessing.Lock()
            setattr(instance, self.LOCK_ATTR, _proxy_lock)

        if exclude_methods is None:
            exclude_methods = []
        for fname, func in iter_methods(instance, exclude=exclude_methods):
            # hijacks the member function
            old_sig = inspect.signature(func)

            if test_bind_partial(func, _client_id_=0):
                def _method(*args,
                            _old_sig_=old_sig,
                            _old_func_=func,
                            **kwargs):
                    # check signature correctness
                    _old_sig_.bind(*args, _client_id_=0, **kwargs)
                    # with _proxy_lock:  # DEPREC
                    return _old_func_(*args, _client_id_=client_id, **kwargs)
            else:
                def _method(*args,
                            _old_sig_=old_sig,
                            _old_func_=func,
                            **kwargs):
                    _old_sig_.bind(*args, **kwargs)  # check signature
                    # with _proxy_lock:  # DEPREC
                    return _old_func_(*args, **kwargs)

            _method.__doc__ = inspect.getdoc(func)  # preserve docstring
            setattr(self, fname, _method)
