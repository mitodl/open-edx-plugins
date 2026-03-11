OL Open edX Course Staff Webhook
#################################

An Open edX plugin that listens for course access role additions and fires a
webhook to notify an external system (e.g. MITx Online) to enroll course staff
as auditors.


Purpose
*******

When an instructor or staff member is added to a course in Open edX (via Studio
or the LMS Instructor Dashboard), this plugin listens for the
``org.openedx.learning.user.course_access_role.added.v1`` event and calls the
MITx Online enrollment webhook to enroll the user as an auditor in the
corresponding course.


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

    MITXONLINE_WEBHOOK_URL: "https://mitxonline.example.com/api/v1/staff_enrollment_webhook/"
    MITXONLINE_WEBHOOK_KEY: "<your-webhook-api-key>"

- Optionally, override the roles that trigger the webhook (defaults to ``["instructor", "staff"]``):

  .. code-block:: yaml

    MITXONLINE_COURSE_STAFF_ROLES: ["instructor", "staff"]

- For Tutor installations, these values can also be managed through a `custom Tutor plugin <https://docs.tutor.edly.io/tutorials/plugin.html#plugin-development-tutorial>`_.
