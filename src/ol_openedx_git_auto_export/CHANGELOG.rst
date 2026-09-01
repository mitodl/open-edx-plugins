Change Log
==========

Version 0.8.4 (2026-09-01)
---------------------------

* Fixed ``export_library_to_git`` scheduling a duplicate ``async_export_to_git``
  task for every ``LIBRARY_BLOCK_PUBLISHED``/``LIBRARY_CONTAINER_PUBLISHED``
  signal, flooding Celery when a course is imported into a v2 library. The
  debounce mechanism previously applied only to course publishes is now shared
  by the library export path.
* Added tests for the export debounce logic.

Version 0.8.2 (2026-06-10)
---------------------------

* Fixed ``migrate_giturl`` management command passing a stale ``export_course``
  keyword to ``async_create_github_repo``, which raised ``TypeError`` during
  parallel repository creation.
* Fixed ``migrate_giturl`` reporting a possibly-unbound loop variable in its
  repository-creation progress message; it now reports the count of courses.
* Added tests for the ``migrate_giturl`` command.
