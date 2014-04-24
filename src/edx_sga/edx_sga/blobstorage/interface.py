import abc


class AbstractBlobStorage(object):
    """
    Defines the interface for a generic blob storage to be implemented by
    concrete implementations.
    """
    __metaclass__ = abc.ABCMeta

    @classmethod
    @abc.abstractmethod
    def factory_from_config(cls, config):
        """
        Returns a no-argument factory function which will return new instances
        of a concrete subclass based on the given configuration.  `config` is a
        dict object containing configuration parameters for creating the
        concrete implementation.  The contents of `config` will depend on the
        concrete implementation.
        """

    @abc.abstractmethod
    def store(self, stream):
        """
        Stores a BLOB by reading from the input stream, `stream`.  Will return
        the sha1 hash of the BLOB, which will then be the key required to
        retrieve the BLOB.
        """

    @abc.abstractmethod
    def retrieve(self, key):
        """
        Retrieves a BLOB given the sha1 hash in `key`.  If the BLOB is not
        found, raises `KeyError`.  Otherwise returns an open input stream from
        which the contents of the BLOB can be read.
        """

    @abc.abstractmethod
    def remove(self, key):
        """
        Removes the BLOB with the specified key from the BLOB storage.
        """
