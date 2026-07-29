# CLAUDE.md — ol_openedx_canvas_integration

An LMS+CMS Django app that links an Open edX course to a Canvas course
(via a `canvas_id` in course Advanced Settings) and keeps them in sync:
pushes graded-subsection assignments and learner grades to Canvas, can
sync/merge/overload enrollments, and optionally pulls assignment due dates
back from Canvas. Adds a "Canvas" tab to the instructor dashboard (both the
legacy Django-rendered dashboard and the OEP-65 `frontend-base` MFE).

## Key files
- `ol_openedx_canvas_integration/client.py`: `CanvasClient` — thin wrapper
  around the Canvas REST API using `requests`, authenticated with
  `CANVAS_ACCESS_TOKEN`/`CANVAS_BASE_URL`.
- `ol_openedx_canvas_integration/api.py`: Course/grade-related helpers, e.g.
  `course_graded_items`, `get_subsection_user_grades` — bridges edx-platform
  grading internals to Canvas payloads.
- `ol_openedx_canvas_integration/tasks.py` / `cms_tasks.py`: Celery tasks —
  `sync_user_grade_with_canvas` (per-learner grade push, LMS), assignment sync
  on publish, `sync_canvas_due_dates_for_all_courses` (CMS, scheduled hourly).
  Split across two files because `cms_tasks.py` must avoid LMS-only settings
  (Celery autodiscovery loads it from the CMS worker too).
- `ol_openedx_canvas_integration/receivers.py` / `handlers.py`:
  `update_grade_in_canvas` — signal receiver on
  `PersistentSubsectionGrade.post_save` that triggers the grade-sync task.
- `ol_openedx_canvas_integration/pipeline.py` +
  `settings/lms/filters.py`: `AddCanvasInstructorTab` — `openedx-filters`
  pipeline step on `InstructorDashboardTabsRequested` that adds the MFE
  "Canvas" tab when `canvas_id` is set.
- `ol_openedx_canvas_integration/context_api.py`: `plugin_context` — legacy
  (non-MFE) instructor-dashboard fragment/context provider.
- `ol_openedx_canvas_integration/views.py` + `urls.py`: instructor-dashboard
  AJAX endpoints (`add_canvas_enrollments`, `list_canvas_enrollments`,
  `list_canvas_assignments`, `list_canvas_grades`, `push_edx_grades`,
  `list_canvas_tasks`), mounted under `courses/<course_id>/canvas/api/`.
- `management/commands/sync_canvas_due_dates.py`: manual/cron entry point for
  due-date sync (`--all` or a specific course).

## Entry points & settings
- Registered for both `lms.djangoapp` and `cms.djangoapp` as
  `ol_openedx_canvas_integration.app:CanvasIntegrationConfig`. LMS also
  registers a `PluginContexts` hook (legacy instructor dashboard fragment) and
  a `PluginSignals` receiver (grade sync).
- Required settings (`CANVAS_ACCESS_TOKEN`, `CANVAS_BASE_URL`) default to
  `None` in common settings and must be supplied via `AUTH_TOKENS`/`ENV_TOKENS`
  in production (`settings/lms/production.py`, `settings/cms/production.py`)
  — without them the plugin is installed but every Canvas API call fails.
  CMS also needs `BULK_EMAIL_MAX_RETRIES`/`BULK_EMAIL_DEFAULT_RETRY_DELAY`
  defined (Celery autodiscovery pulls in LMS task modules).
- CMS common settings register `sync_canvas_due_dates_for_all_courses` in
  `CELERYBEAT_SCHEDULE` to run hourly via Celery beat.
- Production settings for both LMS and CMS must re-call
  `register_instructor_tab_filter`/`apply_common_settings`, because
  edx-platform's production settings overwrite `OPEN_EDX_FILTERS_CONFIG`
  wholesale from deployment YAML, dropping anything registered only in
  common settings.
- Per-course opt-in: course Advanced Settings dict `{"canvas_id": <id>,
  "use_canvas_due_dates": <bool>}` — requires `ENABLE_OTHER_COURSE_SETTINGS`
  feature flag. No `canvas_id` means the course is fully inert for this
  plugin (no tab, no sync).
- Tests: `ol_openedx_canvas_integration/test_settings.py` provides a minimal
  standalone Django settings module (sqlite, no edx-platform) used only by
  this plugin's own `tests/` suite (`pytest`, `--no-migrations --reuse-db`
  per `pyproject.toml`); this is separate from the Tutor-based integration
  tests used for the rest of the plugin's edx-platform-dependent code.

## Notes
- Legacy (Django-rendered) instructor dashboard needs an edx-platform
  cherry-pick (version-dependent commit, see README) to render the Canvas tab
  and surface task status in "Pending Tasks" — **not needed** when running
  only the `frontend-base` instructor dashboard MFE, where this plugin is
  fully self-contained.
- Assignments created in Canvas are always "Unpublished" by default;
  instructors must publish them manually in Canvas for students to see them.
  Updates to existing assignments preserve their published state.
- Grades are not synced to Canvas once the Canvas due date has passed.
