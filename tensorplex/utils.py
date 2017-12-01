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


def iter_methods(obj, exclude=None):
    if exclude is None:
        exclude = []

    for fname in dir(obj):
        func = getattr(obj, fname)
        if (callable(func) and
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


def delegate_methods(cls,
                     transformer,
                     doc_signature=False,
                     exclude_methods=None):
    """
    Args:
        cls: class to be transformed
        transformer: takes an old method and returns the new one (with `self`)
        doc_signature: if True, prepend the signature of the old func to docstring
        exclude_methods:
    """
    assert callable(transformer)
    for fname, func in iter_methods(cls):
        new_func = transformer(func)
        new_func.__name__ = func.__name__
        old_doc = inspect.getdoc(func)
        if doc_signature:
            pass

