ol-openedx-course-staff-webhook
================================

An Open edX plugin that listens for course access role additions and fires a
webhook to notify an external system (e.g. MITx Online) to enroll course staff
as auditors.

Overview
--------

When an instructor or staff member is added to a course in Open edX (via Studio
or the LMS Instructor Dashboard), this plugin listens for the
``org.openedx.learning.user.course_access_role.added.v1`` event and calls the
MITx Online enrollment webhook to enroll the user as an auditor in the
corresponding course.

Configuration
-------------

The following Django settings must be configured:

``MITXONLINE_WEBHOOK_URL``
    The URL of the MITx Online webhook endpoint for course staff enrollment.
    Example: ``https://mitxonline.example.com/api/v1/staff_enrollment_webhook/``

``MITXONLINE_WEBHOOK_KEY``
    An API key or token used to authenticate requests to the MITx Online webhook.

``MITXONLINE_COURSE_STAFF_ROLES``
    A list of course access role strings to act upon. Defaults to
    ``["instructor", "staff"]``.

These settings can be configured in the LMS/CMS environment configuration
(e.g. ``lms.yml`` / ``cms.yml``) under the appropriate tokens.
