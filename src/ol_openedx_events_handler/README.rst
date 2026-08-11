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

- Set the username of the service worker that the external system uses to create
  enrollments through the Open edX enrollment REST API. Enrollments created by
  this user are not sent back to it:

  .. code-block:: yaml

    ENROLLMENT_WEBHOOK_SERVICE_WORKER_USERNAME: "<service-worker-username>"

  This must match the external system's service worker account, for example
  MITx Online's ``OPENEDX_SERVICE_WORKER_USERNAME``. When it is unset, or when
  the acting user cannot be determined (an enrollment made from a Celery task or
  a management command), the webhook is dispatched anyway. The receiving
  endpoint is idempotent, so a redundant call is harmless, while dropping a real
  enrollment is not.

- For Tutor installations, these values can also be managed through a `custom Tutor plugin <https://docs.tutor.edly.io/tutorials/plugin.html#plugin-development-tutorial>`_.
