import inspect
from .utils import iter_methods, test_bind_partial, delegate_methods


class LocalProxy(object):
    """
    Usage: in your server class, add the following method:

    def get_proxy(self, client_id):
        return LocalProxy(self, client_id, exclude_methods=[...])
    """
    def __init__(self, instance, client_id, exclude=None):
        self.client_id = client_id
        delegate_methods(
            target_obj=self,
            src_obj=instance,
            wrapper=self._wrap_method,
            doc_signature=False,
            exclude=exclude
        )

    def _wrap_method(self, fname, old_method):
        old_sig = inspect.signature(old_method)
        if test_bind_partial(old_method, _client_id_=0):
            def _method(*args, **kwargs):
                # check signature correctness
                old_sig.bind(*args, _client_id_=0, **kwargs)
                return old_method(*args, _client_id_=self.client_id, **kwargs)
        else:
            def _method(*args, **kwargs):
                old_sig.bind(*args, **kwargs)  # check signature
                return old_method(*args, **kwargs)
        return _method
