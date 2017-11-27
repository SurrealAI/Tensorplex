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
