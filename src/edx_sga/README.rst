==============================
Staff Graded Assignment XBlock
==============================

This package provides an XBlock for use with the edX platform which provides a
staff graded assignment.  Students are invited to upload files which encapsulate
their work on the assignment.  Instructors are then able to download the files 
and enter grades for the assignment.

Note that this package is both an XBlock and a Django application.  For 
installation:

+ Install this package as an egg into the same environment as the edX platform
  using `pip install`.

+ Add `edx_sga` to `INSTALLED_APPS` in your Django settings.

+ Configure a BLOB storage.  See below.

+ Log in to Studio, navigate to a course you are authoring, and select 
  "Settings" -> "Advanced Settings".  Extend the key "advanced_modules" to 
  include "edx_sga" in the list modules.  
  
"Staff Graded Asssignment" will now be available to add to a course in Studio 
under "Advanced".

BLOB Storage
------------

Files that students upload are stored in a configurable BLOB storage.  The BLOB
storage may be anything which provides the interface expected by the XBlock,
which is defined as an abstract base class in `edx_sga.blobstorage.interface`.
Concrete implementations may derive from `AbstractBlobStorage` in that package,
but are not required to.  You may view the abstract base class as documentation
of the interface expected by code that uses the blob storage.

To configure edX to use a particular BLOB storage, you must provide the variable
`BLOB_STORAGE` in your Django settings.  This variable should point to a factory
callable that doesn't take any arguments and which returns an instance of the 
BLOB storage.

There is currently one concrete BLOB storage implementation provided, which 
stores BLOBs in a folder in the local filesystem.  To configure the BLOB 
storage, you can include the following in your Django settings file::

    from edx_sga.blobstorage.fs import FilesystemBlobStorage
    BLOB_STORAGE = FilesystemBlobStorage.factory_from_config({
        'path': '/path/to/folder'
    })
