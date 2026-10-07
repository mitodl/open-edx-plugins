Change Log
==========

.. There should always be an "Unreleased" section for changes pending release.

Unreleased
----------

Version 0.5.0 (2026-10-01)
---------------------------

* Added the ``sync_course_access_roles`` management command, which sends the
  enrollment webhook for course access roles that already exist. The webhook
  only fires on ``COURSE_ACCESS_ROLE_ADDED``, so a consumer that records those
  roles has no way to learn about the course teams already in place.
* Org-wide roles no longer send the literal string ``"None"`` as the course
  key. ``OrgStaffRole`` and ``OrgInstructorRole`` resolve to ``staff`` and
  ``instructor``, so ``ENROLLMENT_COURSE_ACCESS_ROLES`` let them through, but
  they carry no course key and there is no run to send them against.
* The course access role webhook task no longer retries on ``4xx`` responses,
  except the transient ``408`` and ``429`` — matching the enrollment webhook
  task, which both now share one predicate so they cannot drift apart.

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
