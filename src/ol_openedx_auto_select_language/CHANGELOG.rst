Change Log
----------

..
   All enhancements and patches to ol_openedx_auto_select_language will be documented
   in this file.  It adheres to the structure of https://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (https://semver.org/).
.. There should always be an "Unreleased" section for changes pending release.

Unreleased
~~~~~~~~~~

[0.4.0] - 2026-11-03
~~~~~~~~~~~~~~~~~~~~
Added
-----
* In-place translations mode (``ol_openedx_auto_select_language.in_place_translations``
  course waffle flag): the learner's own language wins, and the course's
  ``BlockTranslation`` rows are shown in it (unit content, outline, sidebar,
  progress, dates, grading type names, video subtitles). Names outside the
  unit are translated in each API response, so the course data the platform
  caches and grades from keeps the source names.
* ``/auto-select-language/api/languages/`` API for the learner language dropdown.

Changed
-------
* Staff paths are matched by whole URL path part, so a block or course id that
  contains "instructor" or "admin" no longer resets the learner's language.
* In in-place mode staff pages are shown in English without saving it.

[0.1.2] - 2026-07-03
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Fixed
-----
* Register the video-language render filter in production settings so it survives
  the deployment's wholesale ``OPEN_EDX_FILTERS_CONFIG`` override in
  ``lms/envs/production.py`` (previously registered only in common settings, so it
  relied on the deployment wiring the filter up).
