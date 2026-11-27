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

Usage
-----

Run on the target instance after importing the course, passing the public
base URL of the source instance's media storage:

.. code-block:: bash

    ./manage.py cms copy_video_thumbnails "course-v1:ORG+NUMBER+RUN" \
        https://xpro-production-edxapp-storage.s3.amazonaws.com/media/

The source objects must be publicly readable. Every MIT OL edxapp storage
bucket allows public reads on ``media/video-images/*``, so no AWS credentials
are needed. Files are written through edx-val's configured image storage
(``VIDEO_IMAGE_SETTINGS``).

For each thumbnail key of the course the command prints one line:

* ``skipped <key>``: already in local storage, never overwritten;
* ``copied <key>``: downloaded from ``<source base URL><key>`` and saved under the same key;
* ``missing <key>: ...``: the download failed, the response wasn't an image
  (usually a wrong base URL), or storage rejected the key. Nothing is saved
  and the other keys still run.

If the course has no thumbnails at all it says so, which usually means the
course key isn't the one on this instance. It is safe to run again, for
example after a re-import.
