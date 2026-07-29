# CLAUDE.md — ol_openedx_git_auto_export

A Studio (CMS) Django app that automatically exports course and content-library OLX to a Git repository whenever an author publishes, and can optionally auto-create the GitHub repository for new courses/libraries. It listens to modulestore/openedx_events publish and creation signals and pushes exports asynchronously via Celery, using edx-platform's own `git_export_utils.export_to_git`.

## Key files
- `ol_openedx_git_auto_export/app.py`: `GitAutoExportConfig` — registers settings and all CMS signal receivers (course publish/created/rerun, library v1 update, library v2 created/updated/block-published/container-published).
- `ol_openedx_git_auto_export/signals.py`: signal handlers that dispatch to `utils.export_course_to_git` / `export_library_to_git` or schedule repo creation.
- `ol_openedx_git_auto_export/tasks.py`: Celery tasks — `async_export_to_git` (runs the actual git export, with stale-lock cleanup) and `async_create_github_repo` (calls the GitHub API, retries on request errors); both treat `ContentNotFoundError` from `get_content_info` as an expected transient race (log a warning and return) rather than a hard failure.
- `ol_openedx_git_auto_export/utils.py`: feature-flag checks (`is_auto_export_enabled`, `is_auto_repo_creation_enabled`), course/library introspection (`get_content_info`, which raises `ContentNotFoundError` rather than returning `None`/a missing object), repo-name slugification, and export debouncing via Django cache.
- `ol_openedx_git_auto_export/exceptions.py`: `ContentNotFoundError` — raised when a course/library can't yet be found in the modulestore or content_libraries API, distinguishing an expected race (content row not committed yet) from a real error.
- `ol_openedx_git_auto_export/models.py`: `ContentGitRepository` — stores `content_key` (course or library key) → `git_url` + `is_export_enabled`, editable via Django admin.
- `ol_openedx_git_auto_export/management/commands/migrate_giturl.py`: one-time command to migrate legacy course `giturl` advanced-settings values into `ContentGitRepository`, creating GitHub repos in parallel for courses that lack one.
- `ol_openedx_git_auto_export/settings/common.py` / `production.py`: wire `FEATURES` flags and `GITHUB_*` / `GIT_REPO_EXPORT_DIR` settings from `ENV_TOKENS`.
- `CONFIGURATION.md`: authoritative reference for every feature flag/setting (mirrors what's summarized below).

## Entry points & settings
- `cms.djangoapp` entry point only (`GitAutoExportConfig`) — this plugin does nothing in LMS.
- Master switch: `FEATURES["ENABLE_EXPORT_GIT"]` must be true, plus the specific flag for the content type:
  - `FEATURES["ENABLE_GIT_AUTO_EXPORT"]` (courses, defaults True) / `FEATURES["ENABLE_GIT_AUTO_LIBRARY_EXPORT"]` (libraries, defaults False).
  - `FEATURES["ENABLE_AUTO_GITHUB_REPO_CREATION"]` (courses) / `FEATURES["ENABLE_AUTO_GITHUB_LIBRARY_REPO_CREATION"]` (libraries) — both default False; enable to auto-create the GitHub repo via API on course/library creation.
- Repo-creation settings: `GITHUB_ORG_API_URL`, `GITHUB_ACCESS_TOKEN` (repo-scoped PAT) — required (raises `ImproperlyConfigured`) if auto-repo-creation is enabled.
- `GIT_REPO_EXPORT_DIR` (default `/openedx/export_course_repos`) — local clone directory used for exports.
- `GIT_AUTO_EXPORT_AUTHORING_URL_PREFIX` (default `authoring`) — URL path prefix used when building a newly-created repo's content URL (`<prefix>/<content_type>/<context_key>`).
- `GIT_EXPORT_DEFAULT_IDENT` (set in `cms/envs/*`, not this plugin) — fallback git commit identity when the publishing user can't be resolved.
- Tests use `ol_openedx_git_auto_export/test_settings.py` (standalone sqlite Django settings, no edx-platform needed for the plugin's own unit tests, e.g. `test_migrate_giturl.py`).

## Notes
- Supports both Library v1 (`library-v1:org+library`, no creation signal — repo is lazily created on first update) and Library v2 (`lib:org:slug`, has both creation and update/block/container-published signals) independently of course export, each behind its own flags.
- Course exports are debounced (via Django cache, see `EXPORT_DEBOUNCE_DELAY`/`EXPORT_DEBOUNCE_CACHE_KEY` in `constants.py`) to coalesce rapid successive publishes into one export.
- `async_export_to_git` clears a stale `.git/index.lock` before exporting to recover from a worker crashing mid-export.
- Course/library-creation signal handlers dispatch `async_create_github_repo` via `transaction.on_commit(...)` instead of calling `.delay()` directly — Studio views run inside `ATOMIC_REQUESTS` transactions, so an immediate dispatch could let the Celery worker query the DB before the new row commits, raising `ContentNotFoundError`.
- Requires GitHub SSH auth configured on the CMS worker/container for `git push` to succeed (see README's "Setup github authentication" section); the GitHub REST API token (`GITHUB_ACCESS_TOKEN`) is only for repo creation, not for pushing.
