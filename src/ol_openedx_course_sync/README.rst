OL Open edX Course Sync
=======================

An Open edX plugin to sync course changes to its reruns.

Version Compatibility
---------------------

It supports Open edX releases from `Sumac` and onwards.

Installing The Plugin
---------------------

For detailed installation instructions, please refer to the `plugin installation guide <../../docs#installation-guide>`_.

Installation required in:

* CMS

Configuration
=============

* Add a setting ``OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME`` for the service worker and all the sync operations will be done on behalf of this user.

  * For Tutor, you can run:

    .. code-block:: bash

       tutor config save --set OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME={USERNAME}

  * If you have a ``private.py`` for the CMS settings, you can add it to ``cms/envs/private.py``.

Usage
-----

* Install the plugin and run the migrations in the CMS.
* Add the parent/source organization in the CMS admin model `CourseSyncOrganization`.
    * Course sync will only work for this organization. It will treat all the courses under this organization as parent/source courses.
* The plugin will automatically add course re-runs created from the CMS as the child courses.
    * The organization can be different for the reruns.
* Target/rerun courses can be managed in the CMS admin model `CourseSyncMapping`.
* Now, any changes made in the source course will be synced to the target courses.
