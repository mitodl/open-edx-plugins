Course Outline API Plugin
=========================

A django app plugin to add a new API to Open edX that returns a course outline summary (one entry
per chapter) for a given course.

Installation
------------

For detailed installation instructions, please refer to the
`plugin installation guide <../../docs#installation-guide>`_.

Installation required in:

* LMS

How To Use
----------

The API supports a GET call to:

- ``<LMS_BASE>/api/course-outline/v0/<course_id>/``

The endpoint is protected by the platform API auth and requires an **admin** user (DRF ``IsAdminUser``).

The successful response for ``http://local.openedx.io:8000/api/course-outline/v0/course-v1:edX+DemoX+Demo_Course/`` would look like:

.. code-block::

    {
        "course_id": "course-v1:edX+DemoX+Demo_Course",
        "generated_at": "2026-03-17T12:34:56Z",
        "modules": [
            {
                "id": "block-v1:edX+DemoX+Demo_Course+type@chapter+block@1414ffd5143b4b5",
                "title": "Example Week 1: Getting Started",
                "effort_time": 121,
                "effort_activities": 1,
                "counts": {
                    "videos": 5,
                    "readings": 3,
                    "problems": 2,
                    "assignments": 1,
                    "app_items": 0
                }
            }
        ]
    }

Notes
-----

- ``generated_at`` is the timestamp when the outline was built (cached responses return the same value).
- ``effort_time`` and ``effort_activities`` come from the platform Effort Estimation transformer via the Blocks API.
- ``counts`` are computed by walking the Blocks API tree under each chapter (staff-only blocks are excluded):
  - ``videos``: blocks with type ``video``
  - ``readings``: blocks with type ``html``
  - ``problems``: blocks with type ``problem``
  - ``assignments``: sequential blocks that are ``graded`` or have a non-empty ``format`` (except ``notgraded``)
  - ``app_items``: leaf blocks that are not ``video``, ``html``, or ``problem`` (and not container types)

Troubleshooting
---------------

- **Page not found (404)**: ensure the plugin is installed in the LMS and the URLs are registered.
- **Course ID in the URL**: course keys contain ``+``. Use URL-encoded form (``%2B``) when needed, e.g.
  ``/api/course-outline/v0/course-v1:OpenedX%2BDemoX%2BDemoCourse/``.
