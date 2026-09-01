Change Log
==========

Version 0.8.4 (2026-09-01)
---------------------------

* Fixed ``export_library_to_git`` running a real git export for every
  ``LIBRARY_BLOCK_PUBLISHED``/``LIBRARY_CONTAINER_PUBLISHED`` signal, flooding
  Celery workers with duplicate git operations when a course is imported into
  a v2 library. A task is still scheduled per signal, but a debounce token
  now ensures only the last one in a burst actually performs the export; the
  same mechanism now covers both the course and library paths.
* Added tests for the export debounce logic.

Version 0.8.2 (2026-06-10)
---------------------------

* Fixed ``migrate_giturl`` management command passing a stale ``export_course``
  keyword to ``async_create_github_repo``, which raised ``TypeError`` during
  parallel repository creation.
* Fixed ``migrate_giturl`` reporting a possibly-unbound loop variable in its
  repository-creation progress message; it now reports the count of courses.
* Added tests for the ``migrate_giturl`` command.
