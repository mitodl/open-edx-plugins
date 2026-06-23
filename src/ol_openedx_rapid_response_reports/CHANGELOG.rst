Change Log
----------

..
   All enhancements and patches to ol_openedx_rapid_response_reports will be documented
   in this file.  It adheres to the structure of https://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (https://semver.org/).

.. There should always be an "Unreleased" section for changes pending release.

Unreleased
~~~~~~~~~~

*

[0.5.0] - 2026-06-22
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Added
-----
* Instructor dashboard MFE support: an ``InstructorDashboardTabsRequested`` filter
  step that adds the "Rapid Responses" tab on deployments where this plugin is
  installed, and a ``rapid_response_runs`` JSON endpoint serving the per-course run
  list rendered by the MFE page. Tab links target
  ``/apps/instructor-dashboard/<course>/<tab>``.
* Declared ``rapid-response-xblock`` as an explicit dependency (the plugin imports
  ``rapid_response_xblock.utils``).

[0.1.0] - 2021-11-17
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Added
_____

* First release on PyPI.
