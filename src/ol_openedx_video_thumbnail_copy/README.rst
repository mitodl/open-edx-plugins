OL Open edX Video Thumbnail Copy
================================

An Open edX CMS plugin that copies a course's video thumbnails from another
Open edX instance's storage after the course was moved over with Studio
export/import.

Course export only carries each thumbnail's storage key
(``video-images/<uuid>.png``), not the image. Import creates the edx-val
``VideoImage`` rows with those keys, but the files stay in the source
instance's bucket, so thumbnails are broken on the target. This plugin
downloads the missing files and saves them under the same keys.

Version Compatibility
---------------------

Supports Open edX releases from **Ulmo** and onwards.

For this plugin's compatibility with Open edX, see the
`Open edX Release Compatibility table <../../docs#open-edx-release-compatibility>`_.

Installing The Plugin
---------------------

For detailed installation instructions, please refer to the
`plugin installation guide <../../docs#installation-guide>`_.

Installation required in:

* CMS

Configuration
-------------

* ``OL_VIDEO_THUMBNAIL_COPY_SOURCE_BASE_URL``: public base URL of the source
  instance's media storage, ending in ``media/``. For example
  ``https://xpro-production-edxapp-storage.s3.amazonaws.com/media/``.
  Optional when ``--source-base-url`` is passed to the command.

The source objects must be publicly readable. Every MIT OL edxapp storage
bucket allows public reads on ``media/video-images/*``, so no AWS credentials
are needed. Files are written through edx-val's configured image storage
(``VIDEO_IMAGE_SETTINGS``).

Usage
-----

Run on the target instance after importing the course:

.. code-block:: bash

    ./manage.py cms copy_xpro_video_thumbnails "course-v1:ORG+NUMBER+RUN"

Options:

* ``--source-base-url URL``: overrides ``OL_VIDEO_THUMBNAIL_COPY_SOURCE_BASE_URL``.
* ``--dry-run``: lists what would be copied without downloading or saving.

For each thumbnail key of the course:

* already present in local storage: skipped, never overwritten;
* missing: downloaded from ``<source base URL><key>`` and saved under the same key;
* download fails (404, server error, timeout): reported as missing.

The command prints the copied, skipped and missing counts, then each missing
key. It is safe to run again, for example after a re-import.
