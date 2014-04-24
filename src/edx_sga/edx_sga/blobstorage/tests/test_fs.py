import os
import shutil
import tempfile
import unittest

from .base import BlobStorageTests
from ..fs import FilesystemBlobStorage


class FilesystemBlobStorageTests(BlobStorageTests, unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.factory = FilesystemBlobStorage.factory_from_config({
            "path": os.path.join(self.tmp, 'test_blobstorage')})

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_fail_to_configure_path(self):
        with self.assertRaises(ValueError):
            FilesystemBlobStorage.factory_from_config({})
