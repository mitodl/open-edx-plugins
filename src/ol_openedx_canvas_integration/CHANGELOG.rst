Change Log
----------

..
   All enhancements and patches to ol_openedx_canvas_integration will be documented
   in this file.  It adheres to the structure of https://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (https://semver.org/).
.. There should always be an "Unreleased" section for changes pending release.

Unreleased
~~~~~~~~~~
* Corrected documentation for due date syncing direction (Canvas to Open edX).
* Updated management command instructions for Tutor.
* Fixed the Tutor patch example in README.rst.

[0.7.0] - 2026-05-12
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Added
-----
* Support for optional Canvas due date syncing.

[0.6.0] - 2025-10-13
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Changed
-------
* Support for Django 5.0.

[0.5.3] - 2025-10-08
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Changed
-------
* Use login_id to match canvas and openedx users.

[0.5.2] - 2025-09-19
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Fixed
-----
* Assignments are now synced with the correct published state.

[0.5.1] - 2025-08-26
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Fixed
-----
* Canvas and Open edX user matching failure due to case-sensitive email comparison.


[0.5.0] - 2025-06-19
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Added
_____

* Automatically update grades in Canvas if the assignments are synced between Open edX and Canvas.
* Automatically sync assignments in Open edX to Canvas when the courses are linked.

[0.0.1] - 2021-10-29
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Added
_____

* First release on PyPI.
