Change Log
==========

.. There should always be an "Unreleased" section for changes pending release.

Unreleased
----------

Version 0.6.0 (2026-10-21)
---------------------------

* Added a receiver for ``ROLE_ASSIGNMENT_CREATED``, the openedx-authz event. A
  course team role granted through edx-platform's own role classes emits
  ``COURSE_ACCESS_ROLE_ADDED`` even with ``authz.enable_course_authoring`` on,
  because ``authz_add_role`` emits it alongside the authz write. A role granted
  through the openedx-authz API directly — the Admin Console's *Assign Role*
  wizard — emits only ``ROLE_ASSIGNMENT_CREATED``, so before this the consumer
  never learned about a course team member added there.
* A grant that emits both events now sends the webhook twice. The consumer
  records the role with ``get_or_create``, so a duplicate is a wasted request
  rather than a wrong one, and missing a role outright is the worse failure.
* The receiver is registered only where ``openedx_events.authz`` exists
  (openedx-events 11.2.0 and later). ``connect_plugin_receivers`` resolves
  every signal path with ``import_string`` and catches nothing, so registering
  it unconditionally would stop the LMS and CMS from starting on releases that
  pin an earlier version, such as Ulmo.
* The CMS signal module moved from ``handlers.course_access_role`` to
  ``handlers.cms``, so it can export both receivers. ``RELATIVE_PATH`` names a
  single module per project type, and the LMS already had ``handlers.lms``.

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
* ``sync_course_access_roles`` skips roles held by inactive users, matching
  ``RoleBase.add_users``, and rejects a malformed ``--course-id`` with a
  ``CommandError`` instead of letting ``InvalidKeyError`` reach the operator.
* The dropped-role log line names ``sync_course_access_roles --course-id`` as
  the recovery, and the README covers two cases a backfill cannot reach: roles
  granted while ``authz.enable_course_authoring`` is on, which write no
  ``CourseAccessRole`` row, and roles granted in Studio before the consumer has
  the run.
* ``sync_course_access_roles`` pages through roles by primary key instead of
  using ``.iterator()``. Celery closes the database connection when a task
  finishes, so on a deployment that runs tasks eagerly that happened inside the
  loop and broke the open cursor with "MySQL server has gone away", ending the
  backfill partway after it had reported what it queued.

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
