ol-openedx-short-video-course
==============================

An Open edX CMS plugin that creates short-video courses directly from a CSV
mapping file.  Each row in the CSV fully describes one unit (section →
subsection → vertical → video block) in the target course.  Multiple courses
can be created in a single command run.

What This Plugin Does
---------------------

- Creates one new course per unique ``course_key`` value in the CSV.
- Builds the full course hierarchy in CSV row order:

  - **Section** (chapter) — one per unique ``section_name`` within a course.
  - **Subsection** (sequential) — one per unique ``subsection_name`` within a section.
  - **Unit** (vertical) — one per row within a subsection.
  - **Video block** — one per unit, pre-loaded with the given ``edx_video_id``.

- Supports a ``--dry-run`` flag to preview the planned structure without writing anything.
- Tracks each run and every created course in audit models available in Django Admin.

CSV Format
----------

The CSV **must** include a header row with these exact column names (order does
not matter)::

    course_name,course_key,section_name,subsection_name,vertical_name,edx_video_id

+------------------+----------------------------------------------------------+
| Column           | Description                                              |
+==================+==========================================================+
| course_name      | Display name of the course to create.                    |
+------------------+----------------------------------------------------------+
| course_key       | Full course key, e.g. ``course-v1:ORG+NUM+RUN``.        |
+------------------+----------------------------------------------------------+
| section_name     | Display name of the section (chapter).                   |
+------------------+----------------------------------------------------------+
| subsection_name  | Display name of the subsection (sequential).             |
+------------------+----------------------------------------------------------+
| vertical_name    | Display name of the unit (vertical) and video block.     |
+------------------+----------------------------------------------------------+
| edx_video_id     | edX VAL video ID for the video block (may be empty).     |
+------------------+----------------------------------------------------------+

Rows with the same ``course_key`` are grouped together.  Within a group, rows
with the same ``section_name`` share one section, and rows with the same
``section_name`` + ``subsection_name`` share one subsection.  All ordering
follows the CSV row order.

Example CSV
~~~~~~~~~~~

.. code-block:: text

    course_name,course_key,section_name,subsection_name,vertical_name,edx_video_id
    Intro to Python,course-v1:MIT+PY101+2T2025,Week 1,Variables,What is a variable?,abc-111
    Intro to Python,course-v1:MIT+PY101+2T2025,Week 1,Loops,For loops explained,abc-222
    Intro to Python,course-v1:MIT+PY101+2T2025,Week 2,Functions,Defining functions,abc-333
    Advanced Python,course-v1:MIT+PY201+2T2025,Module 1,Decorators,Using decorators,xyz-444

Typical Workflow
----------------

1. **Prepare the CSV** with one row per unit, following the schema above.

2. **Dry-run** to validate and preview::

       ./manage.py cms generate_custom_courses \
           --csv-path /path/to/mapping.csv \
           --user-email admin@example.com \
           --dry-run

3. **Create the courses**::

       ./manage.py cms generate_custom_courses \
           --csv-path /path/to/mapping.csv \
           --user-email admin@example.com

Management Commands
-------------------

``generate_custom_courses``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    usage: manage.py cms generate_custom_courses
           --csv-path PATH --user-email EMAIL [--dry-run]

    --csv-path     Path to the CSV mapping file.
    --user-email   Email of the user performing the creation (for audit trail).
    --dry-run      Validate and preview without creating any courses.

Installation
------------

Add the plugin to your Tutor environment and enable it via the
``cms.djangoapp`` entry point configured in ``pyproject.toml``::

    pip install ol-openedx-short-video-course

The plugin's Django app is registered automatically via the CMS plugin
entry point.  Run Django migrations after installation::

    ./manage.py cms migrate

Django Admin
------------

The plugin registers two read-only models in Django Admin:

- **Short Course Creation Jobs** — one record per command invocation.
- **Short Course Variants** — one record per created course, linked to the job.

Development & Testing
---------------------

Tests require an Open edX / Tutor environment.  From inside the LMS container::

    cd /openedx/open-edx-plugins
    ./run_edx_integration_tests.sh --plugin ol_openedx_short_video_course --skip-build
