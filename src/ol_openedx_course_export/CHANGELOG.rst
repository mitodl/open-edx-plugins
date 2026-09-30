Change Log
----------

..
   All enhancements and patches to ol_openedx_course_export will be documented
   in this file.  It adheres to the structure of https://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (https://semver.org/).
.. There should always be an "Unreleased" section for changes pending release.

Unreleased
~~~~~~~~~~

[0.4.1]
~~~~~~~

Fixed
_____

* The export endpoint's route is anchored, so a path under
  ``/api/courses/v0/export/`` that no endpoint serves returns 404 instead of
  being handled as an export request and queuing an export of every course in
  the request body.

[0.4.0]
~~~~~~~

Added
_____

* ``POST /api/courses/v0/export/versions/`` reports, for up to 200 courses at a
  time, the published version together with the static-file and VAL transcript
  facts an export carries but a publish does not move.
