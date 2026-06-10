Change Log
==========

Version 0.8.2 (2026-06-10)
---------------------------

* Fixed ``migrate_giturl`` management command passing a stale ``export_course``
  keyword to ``async_create_github_repo``, which raised ``TypeError`` during
  parallel repository creation.
* Fixed ``migrate_giturl`` reporting a possibly-unbound loop variable in its
  repository-creation progress message; it now reports the count of courses.
* Added tests for the ``migrate_giturl`` command.
