Change Log
==========

Version 0.2.0 (2026-04-17)
---------------------------

* Migrated certificate webhook handling from ``ol_openedx_event_bridge``.
* Added LMS receiver for ``COURSE_GRADE_NOW_PASSED`` to trigger certificate
  creation callbacks in MIT systems.
* Added backward-compatible support for legacy certificate-related env tokens.

Version 0.1.0 (2026-03-17)
---------------------------

* Initial release.
* Handle ``COURSE_ACCESS_ROLE_ADDED`` signal to notify an external system
  of course team additions via webhook.
