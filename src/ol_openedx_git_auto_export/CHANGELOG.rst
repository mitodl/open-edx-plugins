Change Log
==========

Version 0.9.1 (2026-09-22)
---------------------------

* Fixed ``export_library_to_git`` queuing a git export for every
  ``LIBRARY_BLOCK_PUBLISHED``/``LIBRARY_CONTAINER_PUBLISHED`` signal, flooding
  Celery when a course is imported into a v2 library. A burst now queues one
  task, which exports once the signals stop. The course path, which exported a
  mid-burst snapshot 5 seconds after the first signal, uses the same mechanism.
* Export tasks are queued from a ``transaction.on_commit`` hook with
  ``robust=True``. Studio publishes under ``ATOMIC_REQUESTS``, so a task queued
  mid-transaction could wake before the content was visible and give up
  without retrying.
* ``async_create_github_repo``'s post-creation export now goes through the
  debounce instead of running inline, so it coalesces with an import burst
  rather than racing it on the same clone directory. As a result
  ``migrate_giturl`` reports a repository as done once created, not once
  exported.
* Fixed ``get_or_create_git_export_repo_dir`` racing itself when
  ``GIT_REPO_EXPORT_DIR`` does not exist: two processes both passed the
  existence check and the loser's ``FileExistsError`` dropped its export.
* The debounce token's cache key is versioned (``git_export_debounce_v2``) so a
  rollback doesn't see its own short-lived key as claimed by the new token. The
  token is bounded at 7 days rather than permanent.
* The debounce fails open: a dead cache backend queues the export undebounced
  rather than raising into the publish request, and a task that fails to
  enqueue releases its marker so the next signal can retry.
* The publisher lookup runs once per burst instead of once per signal, so a
  large library import no longer issues a ``get_library()`` query per block
  just to discard it.
* Fixed a ``ContentLibraryNotFound`` propagating into the publish request when
  the library row is not visible yet; the export is queued without an author.
* Corrected operator-facing log messages that misreported what happened: a
  parse-failure label on a lookup failure, a retry promise where nothing
  re-queues, a repository-creation claim emitted before the check that skips
  it, and per-signal "starting export" lines during a burst.
* Documented that the debounce needs a cache backend shared between the CMS
  processes and the Celery workers; under ``LocMemCache`` it is inert.
* Added tests for the export debounce logic.

Version 0.9.0 (2026-09-09)
---------------------------

* Raised the Django floor from ``>=4.0`` to ``>=5.2``, making this the minimum
  version for the Ulmo and Verawood releases. See the Open edX Release
  Compatibility table in ``docs/README.rst``.
* The test suite now runs under ``cms.envs.test``; the plugin registers only a
  ``cms.djangoapp`` entry point, so under LMS settings its app is not installed
  and its models and tasks fail to import.

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
