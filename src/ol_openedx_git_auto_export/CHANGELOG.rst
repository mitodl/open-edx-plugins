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
* Export tasks are now queued from a robust ``transaction.on_commit`` hook,
  matching the repository-creation path. Studio publishes under
  ``ATOMIC_REQUESTS``, so a task queued mid-transaction could wake before the
  content was visible and give up without retrying, leaving the publish
  unexported; and without ``robust=True``, one failing hook would have
  cancelled every later signal's hook in the same request.
* The debounce token's cache key is now versioned (``git_export_debounce_v2``)
  so a rollback to 0.8.3 doesn't see its own 5-second key as permanently
  claimed by the new permanent token and silently stop exporting.
* If handing a superseded task's export off to a fresh task fails to enqueue,
  the current task now exports the latest committed state itself instead of
  leaving the newest signal with neither a queued task nor an export.
* Raised the package's declared Django floor to 4.2, the version
  ``transaction.on_commit(..., robust=True)`` requires.
* The publisher lookup now runs only for the signal that queues the task
  instead of once per signal, so a large library import no longer issues
  several ``get_library()`` queries per imported block just to discard them.
* The debounce fails open: a cache backend that is down queues the export
  undebounced instead of raising out of the publish request, and an export task
  that fails to enqueue releases its marker so the next signal can retry.
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
