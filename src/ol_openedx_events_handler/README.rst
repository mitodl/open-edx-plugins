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

- Optionally, override the roles that trigger the webhook (defaults to ``["instructor", "staff"]``):

  .. code-block:: yaml

    ENROLLMENT_COURSE_ACCESS_ROLES: ["instructor", "staff"]

- For Tutor installations, these values can also be managed through a `custom Tutor plugin <https://docs.tutor.edly.io/tutorials/plugin.html#plugin-development-tutorial>`_.
