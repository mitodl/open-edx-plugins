Course Outline API Plugin
=========================

A django app plugin to add a new API to Open edX that returns a course outline summary (one entry
per chapter) for a given course.

Version Compatibility
----------------------

For this plugin's compatibility with Open edX, see the
`Open edX Release Compatibility table <../../docs#open-edx-release-compatibility>`_.

Installation
------------

For detailed installation instructions, please refer to the
`plugin installation guide <../../docs#installation-guide>`_.

Installation required in:

* LMS

How To Use
----------

The API supports a GET call to:

- ``<LMS_BASE>/api/ol-course-outline/v0/<course_id>/``

The endpoint is protected by the platform API auth and requires an **admin** user (DRF ``IsAdminUser``).

The successful response for ``http://local.openedx.io:8000/api/ol-course-outline/v0/course-v1:edX+DemoX+Demo_Course/`` would look like:

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

Caching
-------

This endpoint caches the full JSON response using Django's configured cache backend.

- **TTL**: configurable via ``OL_COURSE_OUTLINE_API_CACHE_TIMEOUT_SECONDS`` (default: 1 week).
- **Cache key**: ``<prefix>s<schema_version>:<course_key>:<content_version>``.
  - ``prefix`` is configurable via ``OL_COURSE_OUTLINE_API_CACHE_KEY_PREFIX`` (default: ``ol_course_outline_api:outline:v0:``).
  - ``schema_version`` is a plugin constant (bump it when you change the response shape or computation logic).
  - ``content_version`` identifies the collected block structure the response was built from: a hash of the same version fields the platform compares in ``BlockStructureStore.is_up_to_date``.
- **Responses that are not cached**: when no collected block structure exists yet, serving the request is what builds it, so no version yet names the content being returned. That response is served uncached and the request after it caches normally.
- **Invalidation**:
  - The response body comes from the collected block structure, which the platform rebuilds asynchronously after a publish (``COURSE_PUBLISH_TASK_DELAY``, 30 seconds by default). The key therefore changes when that rebuild lands, not at publish time. This is deliberate: keying on ``course.course_version`` meant a request arriving inside that window cached pre-publish content under the post-publish key, pinning a stale outline for the full TTL.

Troubleshooting
---------------

- **Page not found (404)**: ensure the plugin is installed in the LMS and the URLs are registered.
- **Course ID in the URL**: course keys contain ``+``. Use URL-encoded form (``%2B``) when needed, e.g.
  ``/api/ol-course-outline/v0/course-v1:OpenedX%2BDemoX%2BDemoCourse/``.
