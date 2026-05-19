Change Log
==========

Version 0.2.1 (2026-05-19)
---------------------------

* Fixed Celery task autodiscovery by adding explicit imports in
  ``tasks/__init__.py`` for all task submodules.

Version 0.2.0 (2026-04-17)
---------------------------

* Added LMS receiver for ``COURSE_GRADE_NOW_PASSED`` to trigger certificate
  creation callbacks in MIT systems.

Version 0.1.0 (2026-03-17)
---------------------------

* Initial release.
* Handle ``COURSE_ACCESS_ROLE_ADDED`` signal to notify an external system
  of course team additions via webhook.
