"""
A concrete implementation of AbstractBlobStorage which stores BLOBs in the
local file system.
"""
import os
import shutil
import uuid

from .interface import AbstractBlobStorage
from .util import HashStream


class FilesystemBlobStorage(AbstractBlobStorage):
    """
    A concrete implementation of AbstractBlobStorage which stores BLOBs in the
    local file system.
    """

    @classmethod
    def factory_from_config(cls, config):
        """
        Creates a new FileSystemBlobStorage factory from a configuration
        dictionary, `config`.  `config` must contain a key, `path`, which
        contains the path on the local filesystem to the folder where BLOBs
        should be stored.  There is also an optional `path` key, which defaults
        to 3, and which indicates how many levels of nesting to use in the
        directory structure for storing BLOBs.  Since not all filesystems
        perform well when directories contain thousands or more files, it is
        often useful to break the storage up into nested folders to make look
        ups faster in the fileystem.  The optimum number of levels is dependent
        on the underlying filesystem and the number of BLOBs being stored.  The
        default, 3, is pretty arbitrary, but should be fine for most cases.
        """
        path = config.get('path')
        if not path:
            raise ValueError(
                "'path' configuration parameter required for {0}".format(cls))
        path = os.path.abspath(path)
        if not os.path.exists(path):
            os.makedirs(path)
        levels = config.get("levels", 3)
        def factory():
            return cls(path, levels)
        return factory

    def __init__(self, path, levels):
        """
        Basic constructor.
        """
        self.path = path
        self.levels = levels

    def store(self, stream):
        """
        See `AbstractBlobStorage`.
        """
        stream = HashStream(stream)
        tmpfile = os.path.join(self.path, str(uuid.uuid4()))
        with open(tmpfile, 'wb') as out:
            shutil.copyfileobj(stream, out)
        key = stream.sha1.hexdigest()
        os.renames(tmpfile, self.path_for(key))
        return key

    def path_for(self, key):
        chunks = ((i * 2, i * 2 + 2) for i in xrange(self.levels))
        folders = [key[begin:end] for begin, end in chunks] + [key]
        return os.path.join(self.path, *folders)

    def retrieve(self, key):
        """
        See `AbstractBlobStorage`.
        """
        path = self.path_for(key)
        if not os.path.exists(path):
            raise KeyError(key)
        return open(path, 'rb')

    def remove(self, key):
        """
        See `AbstractBlobStorage`.
        """
        path = self.path_for(key)
        if not os.path.exists(path):
            raise KeyError(key)
        os.remove(path)
