import hashlib
from itertools import cycle, imap, islice


class BlobStorageTests(object):
    """
    This is an abstract base class for testing concrete implementations of the
    blob storage interface.  Assumes a subclass has provided a factory callable
    at `self.factory` which returns an instance.
    """

    def test_store_and_retrieve(self):
        storage = self.factory()
        expected = DummyFile().read()
        sha1 = hashlib.sha1()
        sha1.update(expected)
        key = storage.store(DummyFile())
        self.assertEqual(key, sha1.hexdigest())
        self.assertEqual(storage.retrieve(key).read(), expected)

    def test_no_such_blob(self):
        with self.assertRaises(KeyError):
            self.factory().retrieve('foo')

    def test_remove(self):
        storage = self.factory()
        key = storage.store(DummyFile())
        storage.remove(key)
        with self.assertRaises(KeyError):
            storage.retrieve(key)

    def test_remove_no_such_blob(self):
        with self.assertRaises(KeyError):
            self.factory().remove('foo')


class DummyFile(object):
    """
    Simulates an arbitrary length input stream which contains the bytes 0..255
    repeated ad infinitum.
    """

    def __init__(self, size=2**20):
        self.i = islice(cycle(imap(chr, xrange(255))), size)

    def read(self, n=None):
        if n is None:
            return ''.join(self.i)
        return ''.join(islice(self.i, n))
