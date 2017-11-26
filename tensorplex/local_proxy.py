import multiprocessing
import inspect


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
        if hasattr(instance, self.LOCK_ATTR):
            _proxy_lock = getattr(instance, self.LOCK_ATTR)
            # protect against both thread and process
            assert isinstance(_proxy_lock, type(multiprocessing.Lock()))
        else:
            _proxy_lock = multiprocessing.Lock()
            setattr(instance, self.LOCK_ATTR, _proxy_lock)

        if exclude_methods is None:
            exclude_methods = []
        for fname in dir(instance):
            func = getattr(instance, fname)
            if (callable(func) and
                    not fname.startswith('_') and
                    not fname in exclude_methods):
                # hijacks the member function
                old_sig = inspect.signature(func)

                def _new_method(*args,
                                __old_sig=old_sig,
                                __old_func=func,
                                **kwargs):
                    __old_sig.bind(*args, **kwargs)  # check signature
                    with _proxy_lock:
                        instance._set_client_id(client_id)
                        return __old_func(*args, **kwargs)
                _new_method.__doc__ = inspect.getdoc(func)  # preserve docstring
                setattr(self, fname, _new_method)
