import os
import binascii
import inspect


def mkdir(fpath):
    """
    Recursively creates all the subdirs
    If exist, do nothing.
    """
    os.makedirs(os.path.expanduser(fpath), exist_ok=True)


def random_string():
    rand_bin = os.urandom(24)
    return binascii.b2a_base64(rand_bin).decode('utf-8')[:-3]  # len 30


def iter_methods(obj, *, exclude=None, include=None):
    if exclude is None:
        exclude = []
    if include is None:
        include = dir(obj)

    for fname in dir(obj):
        func = getattr(obj, fname)
        if (callable(func) and
                fname in include and
                not fname.startswith('_') and
                not fname in exclude):
            yield fname, func


def test_bind_partial(func, *args, **kwargs):
    sig = inspect.signature(func)
    try:
        sig.bind_partial(*args, **kwargs)
        return True
    except TypeError:
        return False


def delegate_methods(*,
                     target_obj,
                     src_obj,
                     wrapper,
                     doc_signature,
                     include=None,
                     exclude=None):
    """
    Args:
        target_obj: class or instance to be transformed
        src_obj: class or instance that gives the original method
        wrapper: takes (fname, func) and returns the new one (with `self`)
        doc_signature: if True, prepend the signature of the old func to docstring
        exclude_methods:
    """
    assert callable(wrapper)
    for fname, func in iter_methods(src_obj, include=include, exclude=exclude):
        new_func = wrapper(fname, func)
        new_func.__name__ = func.__name__
        doc = inspect.getdoc(func)
        if doc is not None and doc_signature:
            sig = str(inspect.signature(func)).replace('(self, ', '(')
            new_func.__doc__ = 'signature: ' + sig + '\n' + doc
        else:
            new_func.__doc__ = doc
        setattr(target_obj, fname, new_func)

