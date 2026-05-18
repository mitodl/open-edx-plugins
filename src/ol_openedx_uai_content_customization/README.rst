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

Original UAI courses are transformed into multiple custom courses per industry
and length combination:

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

1. **Customized video metadata CSV** — produced by the video customization
   workflow. Required columns:

   - ``Course Key`` — the original Open edX course key (e.g.
     ``course-v1:UAI_SOURCE+UAI.2+1T2026``)
   - ``Industry`` — one of: ``Healthcare``, ``Finance``, ``Energy``,
     ``Original industry``
   - ``Duration (Minutes)`` — a numeric value (≤30 = Short) or the literal
     ``long`` (= Full)
   - ``Video File Name`` — file name matching the Name column in the assets CSV
   - ``Video Title (Lecture Title)`` — display name for the subsection/unit/video
   - ``Module Name`` — used to build the course display name

2. **Open edX video asset CSV** — exported from Studio / OVS after uploading
   the customized videos. Required columns:

   - ``Name`` — video file name (matches ``Video File Name`` above)
   - ``Video ID`` — the Open edX UUID for the video

Running the Command
~~~~~~~~~~~~~~~~~~~

Run the management command from inside the CMS container (e.g. Tutor dev
shell):

.. code-block:: bash

    python manage.py generate_uai_courses \
        --customized-csv /path/to/customized.csv \
        --video-assets-csv /path/to/video_assets.csv \
        [--username studio_worker] \
        [--dry-run]

Options
~~~~~~~

``--customized-csv``
    Path to the customized video metadata CSV file. **Required.**

``--video-assets-csv``
    Path to the Open edX video asset CSV file. **Required.**

``--username``
    Username of the platform user under whose authority the courses are
    created. Defaults to ``studio_worker``.

``--dry-run``
    Print what would be created without writing anything to the modulestore.
    Use this to verify CSV mapping before committing.

Development
-----------

.. code-block:: bash

    # Install dependencies
    uv sync --dev

    # Run tests (requires Open edX environment — see AGENTS.md)
    ./run_edx_integration_tests.sh --plugin ol_openedx_uai_content_customization --skip-build
