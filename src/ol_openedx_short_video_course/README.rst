ol-openedx-short-video-course
==============================

An Open edX CMS plugin that generates derived short-video course variants from a
source course using a CSV mapping file.

Each row in the CSV specifies a section and subsection (by usage key), an action
(keep / remove / update), and for update rows, an edX VAL video ID and unit
display name. One destination course is created per unique
``(source_course_key, type, industry_code)`` combination, with the destination
key auto-derived as ``course-v1:ORG+COURSE_NUM.TYPE.INDUSTRY+RUN``.

What This Plugin Does
---------------------

- Clones one source course into one destination per ``(source, type, industry)`` group.
- Applies subsection-level actions from CSV:

  - ``keep``: leave subsection unchanged.
  - ``remove``: delete subsection.
  - ``update``: replace all units in subsection with one vertical containing one video block.

- Validates all groups before writing (all-or-nothing validation).
- Supports a dry run mode to preview planned work.

Typical Workflow
----------------

1. Generate a CSV template from one or more source courses.
2. Fill in ``industry code`` and ``type`` for every row, and set each row action.
3. For rows with ``action=update``, set ``video ID`` and optional ``unit display name``.
4. Run dry run and fix any validation errors.
5. Run live generation.

Management Commands
-------------------

``generate_courses_csv``
    Generates an 8-column CSV template from one or more source courses,
    pre-filled with ``keep`` actions and subsection display names.

``generate_custom_courses``
    Consumes the completed CSV and creates the destination courses.

Command Examples
----------------

Generate a template CSV for one source course:

.. code-block:: bash

    ./manage.py cms generate_courses_csv \
      --source-course-keys course-v1:MITx+6.001x+2026_T1 \
      --output-path /tmp/short-video-mapping.csv

Generate a template for multiple source courses:

.. code-block:: bash

    ./manage.py cms generate_courses_csv \
      --source-course-keys \
        course-v1:MITx+6.001x+2026_T1 \
        course-v1:MITx+6.002x+2026_T1 \
      --output-path /tmp/short-video-mapping.csv

Validate only (no writes):

.. code-block:: bash

    ./manage.py cms generate_custom_courses \
      --csv-path /tmp/short-video-mapping.csv \
      --user-email staff@example.com \
      --dry-run

Generate destination courses:

.. code-block:: bash

    ./manage.py cms generate_custom_courses \
      --csv-path /tmp/short-video-mapping.csv \
      --user-email staff@example.com

CSV Columns
-----------

Required columns:

- ``source_course_key``
- ``section``
- ``subsection``
- ``action``
- ``unit display name``
- ``industry code``
- ``type``
- ``video ID``

Rules:

- ``action`` must be one of ``keep``, ``remove``, ``update``.
- ``video ID`` is required for ``update``.
- ``video ID`` must be empty for ``keep`` and ``remove``.
- ``industry code`` and ``type`` are required for every row.
- Every source subsection must appear exactly once per destination group.

Example CSV
-----------

.. code-block:: csv

    source_course_key,section,subsection,action,unit display name,industry code,type,video ID
    course-v1:MITx+6.001x+2026_T1,block-v1:MITx+6.001x+2026_T1+type@chapter+block@ch1,block-v1:MITx+6.001x+2026_T1+type@sequential+block@seq1,keep,,HC,S,
    course-v1:MITx+6.001x+2026_T1,block-v1:MITx+6.001x+2026_T1+type@chapter+block@ch1,block-v1:MITx+6.001x+2026_T1+type@sequential+block@seq2,remove,,HC,S,
    course-v1:MITx+6.001x+2026_T1,block-v1:MITx+6.001x+2026_T1+type@chapter+block@ch2,block-v1:MITx+6.001x+2026_T1+type@sequential+block@seq3,update,AI in Healthcare Intro,HC,S,aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
    course-v1:MITx+6.001x+2026_T1,block-v1:MITx+6.001x+2026_T1+type@chapter+block@ch1,block-v1:MITx+6.001x+2026_T1+type@sequential+block@seq1,keep,,FN,L,
    course-v1:MITx+6.001x+2026_T1,block-v1:MITx+6.001x+2026_T1+type@chapter+block@ch1,block-v1:MITx+6.001x+2026_T1+type@sequential+block@seq2,update,Risk Modeling Quickstart,FN,L,ffffffff-1111-2222-3333-444444444444

In this example, two destination courses are created:

- ``course-v1:MITx+6.001x.S.HC+2026_T1``
- ``course-v1:MITx+6.001x.L.FN+2026_T1``

Validation and Failure Behavior
-------------------------------

- Validation runs before writes and aggregates all detected issues.
- If validation fails, no destination course is created.
- Live runs are recorded with batch/variant status in admin models:

  - ``ShortCourseCreationJob``
  - ``ShortCourseVariant``

Operational Notes
-----------------

- Register this plugin in CMS only (it is a CMS plugin).
- Run inside an Open edX environment where modulestore and edxval are available.
- If VAL is operationally unavailable, the command fails with an explicit error rather than mislabeling video IDs as invalid.

See the project README for the full CSV format and command reference.
