Changelog
=========

[0.2.0] - 2026-07-07
---------------------

Changed
~~~~~~~
- ``generate_uai_course_versions`` now reads a **single** CSV file instead of
  two.  The ``--edx-videos-csv`` argument has been removed.  Add an
  ``edx_video_id`` column directly to the processed-videos CSV to provide the
  Open edX video UUID for each row.

[0.1.0] - 2026-05-15
---------------------

Added
~~~~~
- Initial release.
- Management command ``generate_uai_course_versions`` to generate industry- and
  length-specific UAI course variants from two CSV files using Open edX
  modulestore APIs.
- CSV utilities for parsing processed video metadata and Open edX video
  exports, and for mapping video file names to Open edX video IDs.
- Modulestore helper functions for course, section, subsection, unit, and
  video block creation.
- ``--dry-run`` flag for safe inspection without writing to the modulestore.
- Full test suite for CSV utilities and the management command.
