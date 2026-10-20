OL Open edX Events Handler
###########################

A generic Open edX plugin for handling Open edX signals and events for
MIT Open Learning.


Purpose
*******

This plugin serves as the centralized handler for all Open edX signals and
events that MIT OL systems need to react to. Rather than creating a separate
plugin for each event, all signal handlers and filters are collected here.

Currently handled events:

* ``org.openedx.learning.user.course_access_role.added.v1`` — When a course
  access role (e.g. instructor, staff) is added, notifies an external system
  via webhook so the user can be enrolled as an auditor in the corresponding
  course.
* ``org.openedx.learning.course.enrollment.created.v1`` — When a user is
  enrolled in a course (for example, when a course team manually enrolls a batch
  of learners from the instructor dashboard), notifies an external system via
  webhook so the enrollment can be mirrored there. Enrollments that the external
  system created itself through the Open edX enrollment REST API are skipped,
  see ``ENROLLMENT_WEBHOOK_SERVICE_WORKER_USERNAME`` below.
* ``openedx.core.djangoapps.signals.signals.COURSE_GRADE_NOW_PASSED`` — When a learner earns a passing grade,
  notifies an external system to create a certificate.


Version Compatibility
======================

For this plugin's compatibility with Open edX, see the
`Open edX Release Compatibility table <../../docs#open-edx-release-compatibility>`_.

Installation
============

For detailed installation instructions, please refer to the `plugin installation guide <../../docs#installation-guide>`_.

Installation required in:

* LMS
* Studio (CMS)


Configuration
=============

edx-platform configuration
---------------------------

- Add the following configuration values to the config file in Open edX. For any release after Juniper, that config file is ``/edx/etc/lms.yml`` and ``/edx/etc/cms.yml``. If you're using ``private.py``, add these values to ``lms/envs/private.py`` and ``cms/envs/private.py``. These should be added to the top level.

  .. code-block:: yaml

    ENROLLMENT_WEBHOOK_URL: "https://example.com/api/openedx_webhook/enrollment/"
    ENROLLMENT_WEBHOOK_ACCESS_TOKEN: "<your-oauth-access-token>"
    CERTIFICATE_WEBHOOK_URL: "https://example.com/api/openedx_webhook/certificate/"
    CERTIFICATE_WEBHOOK_ACCESS_TOKEN: "<your-oauth-access-token>"

- Optionally, override the roles that trigger the webhook (defaults to ``["instructor", "staff"]``):

  .. code-block:: yaml

    ENROLLMENT_COURSE_ACCESS_ROLES: ["instructor", "staff"]

- A consumer that records these roles only hears about new ones, because the
  webhook fires on role addition. Backfill the roles that already exist once,
  after deploying such a consumer:

  .. code-block:: shell

    ./manage.py lms sync_course_access_roles --dry-run
    ./manage.py lms sync_course_access_roles

  Pass ``--course-id`` (repeatable) to limit the backfill to specific courses.

  The command reports what it **queued**, not what was delivered: each role is
  handed to Celery, and a task that exhausts its retries is logged rather than
  reported back. It is safe to re-run, because the consumer is expected to
  upsert on the user, run and role, so re-run it if the logs show failures.

  Re-running is also the fix for a role granted before the consumer knew about
  the run. Studio emits ``COURSE_ACCESS_ROLE_ADDED`` for the creator as soon as
  a run is created or rerun, which is usually before the consumer has a record
  of that run, so the webhook is rejected with a 404 and the role is dropped
  rather than retried. Once the run exists there, run::

    ./manage.py lms sync_course_access_roles --course-id <course key>

  Two kinds of grant are invisible to this command. Org-wide roles are skipped
  deliberately, as above. The other is a consequence of openedx-authz: once
  ``authz.enable_course_authoring`` is on for a course, ``RoleBase.add_users``
  routes through authz and writes no ``CourseAccessRole`` row, so a role
  granted from then on is not something this command can read.

  Roles granted *before* that are still readable. ``authz_migrate_course_authoring``
  copies them into authz but keeps the legacy rows unless it is run with
  ``--delete``, so the course teams this command exists to catch up remain in
  ``CourseAccessRole``.

  The live webhook is unaffected either way: Open edX emits
  ``COURSE_ACCESS_ROLE_ADDED`` for an authz grant too, so the receiver still
  fires and the consumer still records the role. Only catching up after the
  fact is affected -- which matters for the 404 case above, because re-running
  this command will not recover a role granted on an authz-enabled course.
  Covering those needs the command to read role assignments from authz as well,
  which it does not do yet.

- Set the username of the service worker that the external system uses to create
  enrollments through the Open edX enrollment REST API. Enrollments created by
  this user are not sent back to it:

  .. code-block:: yaml

    ENROLLMENT_WEBHOOK_SERVICE_WORKER_USERNAME: "<service-worker-username>"

  This must be the username of the Django user that **owns the OAuth2 token**
  the external system authenticates with, because that is the user Open edX
  resolves the request to. Do not copy the external system's own
  service-worker-username setting (for example MITx Online's
  ``OPENEDX_SERVICE_WORKER_USERNAME``): nothing keeps the two in sync, and if
  they disagree the filter never matches and every enrollment the external
  system creates is sent straight back to it. Resolve the owner from the token
  itself:

  .. code-block:: python

    from oauth2_provider.models import AccessToken
    AccessToken.objects.get(token="<the external system's API token>").user.username

  When the setting is unset, or when the acting user cannot be determined (an
  enrollment made from a Celery task or a management command), the webhook is
  dispatched anyway. The receiving endpoint is idempotent, so a redundant call
  is harmless, while dropping a real enrollment is not.

- For Tutor installations, these values can also be managed through a `custom Tutor plugin <https://docs.tutor.edly.io/tutorials/plugin.html#plugin-development-tutorial>`_.
