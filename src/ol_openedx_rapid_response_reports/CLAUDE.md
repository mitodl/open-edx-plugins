# CLAUDE.md — ol_openedx_rapid_response_reports

An LMS Django app that adds a "Rapid Responses" tab/section to the Instructor Dashboard, letting staff list rapid-response problem runs for a course and download a CSV of submissions. It's a thin reporting layer on top of the separate `rapid-response-xblock` package (a workspace dependency here), which owns the actual data model for runs/submissions.

## Key files
- `ol_openedx_rapid_response_reports/api.py`: the two JSON/CSV views — `list_rapid_response_runs` (JSON list of runs, consumed by the instructor dashboard MFE) and `get_rapid_response_report` (CSV download for a given `run_id`), both gated by `require_course_permission(VIEW_DASHBOARD)`.
- `ol_openedx_rapid_response_reports/pipeline.py`: `AddRapidResponseInstructorTab`, an Open edX Filters `PipelineStep` hooking `org.openedx.learning.instructor.dashboard.tabs.requested.v1` to append the "Rapid Responses" tab (MFE path) to the instructor dashboard tab list — this is the modern (MFE) integration path.
- `ol_openedx_rapid_response_reports/context_api.py`: `plugin_context()` — the legacy (non-MFE) instructor-dashboard "PluginContexts" integration that appends a `rapid_response` section with an inline Fragment.
- `ol_openedx_rapid_response_reports/settings/filters.py`: `register_instructor_tab_filter()` — idempotently merges the pipeline step into `OPEN_EDX_FILTERS_CONFIG`; called from both common and production settings because production overwrites `OPEN_EDX_FILTERS_CONFIG` wholesale from deployment YAML.
- `ol_openedx_rapid_response_reports/urls.py`: `rapid_response_runs` and `rapid_response_report/<run_id>` routes, mounted under the instructor API namespace.
- `ol_openedx_rapid_response_reports/utils.py`: `get_display_name_from_usage_key` helper for labeling runs.
- `ol_openedx_rapid_response_reports/templates/rapid_response.html`: template for the legacy dashboard section fragment.
- `ol_openedx_rapid_response_reports/app.py`: `RapidResponsePluginConfig` — registers URLs (under `courses/<course_id>/instructor/api/`), settings, and the `PluginContexts` hook (`INSTRUCTOR_DASHBOARD_PLUGIN_VIEW_NAME`) for LMS.

## Entry points & settings
- `lms.djangoapp` entry point only (`RapidResponsePluginConfig`); no CMS component.
- Both integration paths (legacy `PluginContexts` section and modern MFE tab via Open edX Filters) are registered simultaneously — which one is actually visible depends on which instructor dashboard (legacy Django template vs. MFE) the deployment runs.
- `settings/production.py`: re-registers the tab filter (see gotcha below) and appends the plugin's `templates/` dir to `TEMPLATES[*]["DIRS"]`.
- Depends on the `rapid-response-xblock` package (must be installed; declared as a `uv` workspace source here) for `get_run_data_for_course` / `get_run_submission_data`.
- No standalone test settings module — imports `lms.djangoapps.*` directly (courseware, instructor, instructor_analytics), so tests require the full edx-platform environment (Tutor), consistent with `pytest` opts `--no-migrations --reuse-db` in `pyproject.toml`.

## Notes
- **Gotcha already fixed once (0.5.1)**: `OPEN_EDX_FILTERS_CONFIG` gets wholesale-replaced by `lms/envs/production.py` from deployment YAML, which would silently drop the tab registered only in common settings — hence `register_instructor_tab_filter` is called again from `production.py`. If you touch filter registration, preserve this double-registration.
- The MFE tab URL is built from `settings.INSTRUCTOR_MICROFRONTEND_URL`'s path component (see `pipeline.build_instructor_dashboard_tab_url`) rather than hardcoding `/apps`, so it stays consistent with built-in tabs.
- README notes that Open edX releases prior to Nutmeg require a specific edx-platform cherry-pick for the tab to appear at all; Nutmeg+ works out of the box with plugin version >= 0.2.0.
- Legacy `context_api.plugin_context` always appends the section unconditionally (no per-course gating) — the pipeline step mirrors that behavior for the MFE path.
