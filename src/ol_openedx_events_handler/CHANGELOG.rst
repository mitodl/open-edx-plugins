Change Log
==========

Version 0.3.0 (2026-08-11)
---------------------------

* Added LMS receiver for ``COURSE_ENROLLMENT_CREATED`` to mirror Open edX
  enrollments (including manual instructor dashboard enrollments) in MIT
  systems via the enrollment webhook.
* Enrollments created by the webhook consumer's own service worker are skipped,
  configured through ``ENROLLMENT_WEBHOOK_SERVICE_WORKER_USERNAME``.
* The enrollment webhook task no longer retries on ``4xx`` responses, except
  the transient ``408`` and ``429``.

Version 0.2.1 (2026-05-19)
---------------------------

* Fixed Celery task autodiscovery by flattening the ``tasks/`` package
  into a single ``tasks.py`` module.

Version 0.2.0 (2026-04-17)
---------------------------

* Added LMS receiver for ``COURSE_GRADE_NOW_PASSED`` to trigger certificate
  creation callbacks in MIT systems.

Version 0.1.0 (2026-03-17)
---------------------------

* Initial release.
* Handle ``COURSE_ACCESS_ROLE_ADDED`` signal to notify an external system
  of course team additions via webhook.
