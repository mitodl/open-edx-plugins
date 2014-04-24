import hashlib


class HashStream(object):
    """
    A file-like object that wraps another stream accumulates an SHA1 hash as
    bytes are read out of it.
    """
    def __init__(self, wrapped):
        self.wrapped = wrapped
        self.sha1 = hashlib.sha1()

    def read(self, n=None):
        block = self.wrapped.read(n)
        self.sha1.update(block)
        return block
