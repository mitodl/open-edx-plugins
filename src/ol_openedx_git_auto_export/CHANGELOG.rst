Change Log
==========

Version 0.8.4 (2026-09-01)
---------------------------

* Fixed ``export_library_to_git`` queuing a git export for every
  ``LIBRARY_BLOCK_PUBLISHED``/``LIBRARY_CONTAINER_PUBLISHED`` signal, flooding
  Celery with duplicate export tasks when a course is imported into a v2
  library. A burst of signals now queues a single task, which exports once the
  signals stop and re-queues itself while they are still arriving, so the
  export reflects the end of the import rather than a mid-import snapshot. The
  same mechanism covers the course path, which previously exported whatever
  state existed 5 seconds after the first signal of a burst.
* Fixed a ``ContentLibraryNotFound`` from ``export_library_to_git`` propagating
  into the publish request when the library row is not visible yet; the export
  is now queued without a commit author instead.
* Added tests for the export debounce logic.

Version 0.8.3 (2026-08-03)
---------------------------

* Fixed a race where an export task could run before the library was committed
  to the store, reporting a spurious "library not found".

Version 0.8.2 (2026-06-10)
---------------------------

* Fixed ``migrate_giturl`` management command passing a stale ``export_course``
  keyword to ``async_create_github_repo``, which raised ``TypeError`` during
  parallel repository creation.
* Fixed ``migrate_giturl`` reporting a possibly-unbound loop variable in its
  repository-creation progress message; it now reports the count of courses.
* Added tests for the ``migrate_giturl`` command.
