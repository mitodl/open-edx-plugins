OL Open edX UAI Content Customization
======================================

An Open edX CMS plugin that automates the generation of industry- and
length-specific UAI course variants using direct Open edX modulestore APIs.

Version Compatibility
---------------------

Supports Open edX releases from **Sumac** and onwards.

Installing The Plugin
---------------------

For detailed installation instructions, please refer to the
`plugin installation guide <../../docs#installation-guide>`_.

Installation required in:

* CMS

Overview
--------

For each unique (course_key, industry, duration) row group in the CSV the
command clones the source course into a new UAI-specific key, removes every
existing section from the clone, and rebuilds the content from the CSV data.
This produces multiple industry- and length-specific variants per source
course while preserving all course settings (grading policy, certificates,
pacing, advanced settings) from the original.

Supported industry/length combinations:

+--------------+------+-------------+--------+
| Industry     | Code | Length code | Length |
+==============+======+=============+========+
| Healthcare   | HC   | S           | Short  |
+--------------+------+-------------+--------+
| Healthcare   | HC   | F           | Full   |
+--------------+------+-------------+--------+
| Finance      | F    | S           | Short  |
+--------------+------+-------------+--------+
| Finance      | F    | F           | Full   |
+--------------+------+-------------+--------+
| Energy       | E    | S           | Short  |
+--------------+------+-------------+--------+
| Energy       | E    | F           | Full   |
+--------------+------+-------------+--------+
| Original     | —    | S           | Short  |
+--------------+------+-------------+--------+
| Original     | —    | F           | Full   |
+--------------+------+-------------+--------+

Course Key Format
~~~~~~~~~~~~~~~~~

.. code-block:: text

    course-v1:ORG+NUMBER.<DURATION>[.<INDUSTRY>]+RUN

For the **Original** industry, no industry code is appended:

.. code-block:: text

    course-v1:UAI_SOURCE+UAI.3.S+1T2026   ← Original, Short
    course-v1:UAI_SOURCE+UAI.3.F+1T2026   ← Original, Full
    course-v1:UAI_SOURCE+UAI.3.S.HC+1T2026 ← Healthcare, Short

Course Structure
~~~~~~~~~~~~~~~~

Each generated course has the following structure::

    Course (<display name>)
    └── Lectures  (section)
        └── <Video Title>  (subsection)
            └── <Video Title>  (unit)
                └── <Video Title>  (video block with edX video ID)

Usage
-----

Prerequisites
~~~~~~~~~~~~~

You will need two CSV files:

1. **Processed videos CSV** — produced by the video customization
   workflow. Required columns:

   - ``course_key`` — the Open edX course key of the **source course to
     clone** (e.g. ``course-v1:UAI_SOURCE+UAI.2+1T2026``).  This course
     **must already exist** in the CMS modulestore before the command runs.
     The command validates all source keys up-front and aborts with an error
     if any are missing.
   - ``industry`` — one of: ``Healthcare``, ``Finance``, ``Energy``,
     ``Original industry``
   - ``duration`` — ``short`` or ``long``
   - ``video_file_name`` — file name matching the ``name`` column in the edX videos CSV
   - ``video_title`` — display name for the subsection/unit/video
   - ``module_name`` — used to build the course display name

2. **Open edX videos CSV** — exported from Studio / OVS after uploading
   the customized videos. Required columns:

   - ``name`` — video file name (matches ``video_file_name`` above)
   - ``video_id`` — the Open edX UUID for the video

Running the Command
~~~~~~~~~~~~~~~~~~~

Run the management command from inside the CMS container (e.g. Tutor dev
shell):

.. code-block:: bash

    python manage.py generate_uai_course_versions \
        --processed-videos-csv /path/to/processed_videos.csv \
        --edx-videos-csv /path/to/edx_videos.csv \
        [--username studio_worker] \
        [--dry-run]

Options
~~~~~~~

``--processed-videos-csv``
    Path to the processed video metadata CSV file. **Required.**

``--edx-videos-csv``
    Path to the Open edX videos CSV file. **Required.**

``--username``
    Username of the platform user under whose authority the courses are
    created. Defaults to ``studio_worker``.

``--dry-run``
    Print what would be created without writing anything to the modulestore.
    Use this to verify CSV mapping before committing.

How It Works
~~~~~~~~~~~~

For each unique ``(course_key, industry, duration)`` group the command:

1. **Validates** all source course keys against the live modulestore before
   making any writes (fail-fast — aborts if any source is missing).
2. **Clones** the source course into the new UAI-specific key, inheriting all
   course settings.
3. **Deletes** every existing section (chapter) from the clone.
4. **Rebuilds** the content tree from the CSV rows::

       Course  (cloned — settings inherited)
       └── Lectures  (section)
           └── <Video Title>  (subsection)
               └── <Video Title>  (unit)
                   └── <Video Title>  (video block)

5. **Publishes** the course.

.. note::

   Course creation is **not atomic** (MongoDB is not covered by Django
   transactions).  If a run fails partway through, already-created courses
   remain; subsequent runs will skip them with a ``DuplicateCourseError``
   warning.

Development
-----------

.. code-block:: bash

    # Install dependencies
    uv sync --dev

    # Run tests (requires Open edX environment — see AGENTS.md)
    ./run_edx_integration_tests.sh --plugin ol_openedx_uai_content_customization --skip-build
