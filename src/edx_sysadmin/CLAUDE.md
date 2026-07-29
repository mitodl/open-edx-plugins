# CLAUDE.md — edx_sysadmin

An LMS+CMS Django app that restores the "Sysadmin Dashboard" removed from
edx-platform core after the Lilac release. It gives designated staff a UI
(`<LMS_BASE>/sysadmin`) to register users, delete courses, and import courses
from git repositories (including via GitHub webhooks), replacing the old
`ENABLE_SYSADMIN_DASHBOARD` feature-flagged panel for Lilac and later.

## Key files
- `edx_sysadmin/views.py`: Panel views — `SysadminDashboardRedirectionView`,
  users/courses/git-import/git-logs tabs. Access gated by
  `user_has_access_to_*` helpers in `utils/utils.py`.
- `edx_sysadmin/git_import.py`: Core git-import logic (`GitImportError`,
  clone/checkout/import-into-modulestore flow), ported from edx-platform.
- `edx_sysadmin/models.py`: `CourseGitLog` — stores git-log/import-log history
  per course (`course_id`, `course_import_log` JSON, `git_log`, `commit`,
  `author`).
- `edx_sysadmin/api/views.py` + `api/urls.py`: `GitReloadAPIView` (GitHub
  webhook receiver for auto reload-on-push) and `GitCourseDetailsAPIView`.
  `api/permissions.py` guards webhook auth via `SYSADMIN_GITHUB_WEBHOOK_KEY`.
- `edx_sysadmin/management/commands/git_add_course.py`: CLI equivalent of the
  Git Import panel.
- `edx_sysadmin/settings/common.py`: `plugin_settings` — defines the plugin's
  settings defaults (see below).
- `edx_sysadmin/forms.py`, `templates/edx_sysadmin/*.html`: user-registration
  form and the four dashboard tab templates.

## Entry points & settings
- Registered for both `lms.djangoapp` and `cms.djangoapp` as
  `edx_sysadmin.apps:EdxSysAdminConfig`; URLs mounted under `^sysadmin/` in LMS
  only (`url_config` in `apps.py`).
- Settings (`settings/common.py`, all overridable via `lms.yml`/`private.py`):
  `GIT_REPO_DIR` (default `/openedx/course_repos`), `GIT_IMPORT_STATIC`
  (default `True`), `GIT_IMPORT_PYTHON_LIB` (default `True`),
  `SYSADMIN_GITHUB_WEBHOOK_KEY` (default `None`, sha1/sha256 webhook secret),
  `SYSADMIN_DEFAULT_BRANCH` (default `None`, branch used on webhook reload).
- Tests: `DJANGO_SETTINGS_MODULE = lms.envs.test` (`setup.cfg`), run via the
  repo's Tutor integration harness.

## Notes
- Requires the `/openedx/course_repos` directory to exist inside the LMS
  container before first use (`mkdir /openedx/course_repos`).
- Has a `CourseGitLog` model with migrations (`edx_sysadmin/migrations/`) — a
  schema change here needs a new migration, not a settings tweak.
- The GitHub webhook path only works if `SYSADMIN_GITHUB_WEBHOOK_KEY` is
  configured; without it the reload API still exists but signature
  verification will reject requests.
- Uses internal edx-platform imports (`common.djangoapps.student.roles`,
  `xmodule.modulestore.django`, `cms.djangoapps.contentstore.outlines`), so
  it's coupled to edx-platform internals and only meant to run inside it.
