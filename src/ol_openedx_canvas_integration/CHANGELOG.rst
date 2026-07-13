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

[0.8.2] - 2026-07-13
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Fixed
-----
* Due date sync no longer crashes with ``TypeError: fromisoformat: argument must
  be str`` when a Canvas assignment override sets only an "Until" date (``lock_at``)
  with no "Due" date. Such overrides have ``due_at: None`` and are now skipped
  instead of being passed to ``parse_datetime``.

[0.8.1] - 2026-07-03
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Fixed
-----
* Re-register the instructor dashboard tab filter in production settings so the
  "Canvas" tab survives the deployment's wholesale ``OPEN_EDX_FILTERS_CONFIG``
  override in ``lms/envs/production.py`` (the filter was previously registered
  only in common settings).

[0.8.0] - 2026-06-22
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Added
-----
* Instructor dashboard MFE support: an ``InstructorDashboardTabsRequested`` filter
  step that adds the "Canvas" tab only for courses linked to Canvas (``canvas_id``
  set), and a ``list_canvas_tasks`` JSON endpoint the MFE polls for Canvas task
  status. Tab links target ``/apps/instructor-dashboard/<course>/<tab>``. This
  removes the need for the edx-platform cherry-pick when running the frontend-base
  instructor dashboard (see README).

[0.7.0] - 2026-05-12
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Added
-----
* Support for optional Canvas due date syncing.
* Corrected documentation for due date syncing direction (Canvas to Open edX).
* Updated management command instructions for Tutor.
* Fixed the Tutor patch example in README.rst.

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
