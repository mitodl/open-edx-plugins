================================
Course Outline API Plugin
================================

**Plan (what can be done this way):** One public endpoint returns per-module (chapter)
title, effort time, and counts. We **do not have** a module summary/description (Open edX
has no such field). For **time**: we can use the platform’s effort only for **videos** (and
readings); there is **no mechanism** to count time for assignments. Counts come from the
Blocks API: **videos** = ``video`` blocks, **readings** = ``html`` blocks, **assignments** =
graded sequentials (count), **app_items** = other leaf blocks (not video/html/problem).
Visibility and effort follow platform settings; no new storage.

**Endpoint:** ``GET /api/course-outline/v0/{course_id}/``

Installation
------------

For detailed installation instructions, please refer to the
`plugin installation guide <../../docs#installation-guide>`_.

Installation required in:

* LMS

The plugin must be **installed** in the LMS so it is in ``INSTALLED_APPS`` and its URLs are registered.

- **Tutor:** Add the package to your Tutor config so it is installed in the LMS container (e.g. ``OPENEDX_PLUGINS`` or a custom requirements file, then ``tutor images build openedx`` and restart). If you mount the repo, run ``pip install -e /path/to/open-edx-plugins/src/ol_openedx_course_outline_api`` inside the LMS container.
- **Standalone:** ``pip install ol-openedx-course-outline-api`` (or install from the repo). Ensure the LMS ``INSTALLED_APPS`` includes the plugin (auto-added when installed via the ``lms.djangoapp`` entry point).

----------------------------------------------------------------------------
Troubleshooting: Page not found (404)
----------------------------------------------------------------------------

- **Plugin not installed:** If the plugin is not installed in the LMS, no URL pattern is registered and you get a 404. Confirm the package is installed (e.g. ``pip list | grep course-outline``) and that the app is loaded (e.g. in Django shell: ``from django.conf import settings; "ol_openedx_course_outline_api" in settings.INSTALLED_APPS``).
- **Course ID in the URL:** Course keys contain ``+`` (e.g. ``course-v1:OpenedX+DemoX+DemoCourse``). In URLs, ``+`` can be interpreted as a space. Use **URL-encoded** form: ``course-v1:OpenedX%2BDemoX%2BDemoCourse``. Example: ``GET /api/course-outline/v0/course-v1:OpenedX%2BDemoX%2BDemoCourse/``.

----------------------------------------------------------------------------
What does the API return?
----------------------------------------------------------------------------

We do **not** have a module summary or description (Open edX does not expose that for
chapters). The response is one JSON object per request with:

- **course_id** – Course key (e.g. ``course-v1:Org+Course+Run``).
- **generated_at** – ISO timestamp when the outline was built.
- **modules** – List of modules (one per Open edX **chapter**), each with:
  - **id** – Chapter block usage key.
  - **title** – Chapter display name.
  - **effort_time** – Total estimated time for the chapter (seconds) as returned by the Blocks API.
  - **effort_activities** – Number of activities that the effort system counted when computing ``effort_time``.
  - **counts** – Object with **videos**, **readings**, **assignments**, **app_items** (integers).

The front end can format ``effort_time`` (e.g. hours/minutes) and combine title
and counts into a line like "Module 1: Introduction — 5 videos, 3 readings, 1 assignment, 2 activities" (time only reflects video + reading; no assignment time).

----------------------------------------------------------------------------
How is estimated time (effort_time) obtained?
----------------------------------------------------------------------------

**Where it comes from:** We use the Open edX **EffortEstimationTransformer** (Blocks API).
We **can** count time for **videos** (duration from video pipeline/edxval); the platform
also estimates **reading** time from HTML word count. It does **not** provide time for
assignments or other block types. At the chapter level, ``effort_time`` is
the platform’s aggregate of video + reading time only. There is no fallback; if the
platform returns 0, we return 0.

**How to get non-zero values:** See the section *How to get non-zero effort_time?* below (publish, video durations, waffle flag).

**What about time for assignments?** There is **no mechanism** in Open edX to set or
derive time for assignments/subsections. We only have **effort_time** (video +
reading). **counts.assignments** is the number of graded sequentials, not a duration.

----------------------------------------------------------------------------
How are the content counts (mappings) done?
----------------------------------------------------------------------------

We call the **Blocks API** (``get_blocks``) with ``block_counts=["video", "html", "problem"]``
and use the block tree under each chapter. Mappings:

- **videos** – Blocks with type ``video`` under the chapter (Blocks API ``block_counts.video``).
- **readings** – Blocks with type ``html`` under the chapter (``block_counts.html``).
- **assignments** – Count of sequentials that are graded or have an assignment type. We treat a sequential as an assignment if ``graded == True`` **or** if it has a non-empty **format** (e.g. Homework, Lab, Midterm Exam, Final Exam). The Blocks API can return ``graded: false`` even when the subsection is linked to an assignment in Studio; we request ``format`` and use it as a fallback so those still count.
- **app_items** – **Leaf** blocks (no children) whose type is not ``video``, ``html``, or ``problem``, and not a container (``course``, ``chapter``, ``sequential``, ``vertical``)—e.g. custom XBlocks, drag-and-drop.
- **asktim** – Number of video/problem blocks under the chapter that have **Enable AI Chat Assistant** on (ol_openedx_chat aside). 0 if the plugin is not installed.

----------------------------------------------------------------------------
How to get non-zero effort_time?
----------------------------------------------------------------------------

The platform only fills ``effort_time`` when the EffortEstimationTransformer runs and has enough data. Do the following.

**1. Re-publish the course**

Block structure (and effort) is updated on course publish. In **Studio**, open the course and use **Publish**. After the background task completes (often within a minute), chapter-level ``effort_time`` is available. Re-publish again after changing content or fixing video durations.

**2. Ensure every video has a duration**

The transformer uses the video pipeline (e.g. edxval). If *any* course video has missing or zero duration, the transformer disables estimation for the **entire** course. Use **Video Uploads** in Studio (or your pipeline) so every video has duration metadata; fix or re-process any video that does not.

**3. Leave effort estimation enabled for the course**

The course-level waffle flag ``effort_estimation.disabled`` must be **off** for the course.

- **Django Admin:** **Waffle Utils > Waffle flag course overrides**. If there is an override for ``effort_estimation.disabled`` and your course, set **Override choice** to **Force Off**. If there is no override, estimation is enabled by default.
- Do not force the flag **On** for this course, or ``effort_time`` will stay 0.

When all three are done, the API will return non-zero ``effort_time`` when the Blocks API provides them.
