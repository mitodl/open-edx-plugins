# CLAUDE.md — rapid_response_xblock

An XBlock **aside** (not a standalone XBlock) that adds live "rapid response"
polling to multiple-choice problem blocks: staff can open/close a problem for
a timed window, and student submissions during that window are aggregated
and shown as a real-time bar chart (D3) to staff. Installs into both LMS
(student-facing polling UI + submission capture) and CMS/Studio (an
opt-in author toggle and a Plugins-tab setting per problem).

## Key files
- `rapid_response_xblock/block.py`: `RapidResponseAside` (`XBlockAside`) — the `enabled` field gates whether rapid-response UI shows on a problem; `student_view_aside`/`author_view_aside`/`studio_view_aside` render fragments; `toggle_block_open_status` (staff-only handler) opens/closes a `RapidResponseRun`. Only applies to `multiplechoiceresponse` problems (`MULTIPLE_CHOICE_TYPE`).
- `rapid_response_xblock/models.py`: `RapidResponseRun` (one open/close window per problem) and `RapidResponseSubmission` (one row per student submission during an open run, storing the raw tracking event JSON).
- `rapid_response_xblock/logger.py`: `SubmissionRecorder`, an `EVENT_TRACKING_BACKENDS` backend — parses `problem_check` tracking events, and if there's an open `RapidResponseRun` for that problem, records (replacing any prior) submission for that user.
- `rapid_response_xblock/settings/common.py`: registers `SubmissionRecorder` under `EVENT_TRACKING_BACKENDS["rapid_response"]` (LMS).
- `rapid_response_xblock/settings/cms_settings.py`: sets `ENABLE_RAPID_RESPONSE_AUTHOR_VIEW = False` by default (CMS).
- `rapid_response_xblock/migrations/`: 5 migrations for the two models above (renamed fields, added `open`/status, dropped a `run_name` field along the way — check these before assuming current model shape from memory).
- `rapid_response_xblock/static/`: `rapid.html`/`rapid.js` (LMS live-poll UI, D3 bar chart) and `rapid_studio.html`/`rapid_studio.js` (Studio toggle UI).
- `tests/test_aside.py`, `tests/test_events.py`, `tests/test_utils.py`: unit tests; `test_data/2017_SGA/`: an XML course fixture used by tests.

## Entry points & settings
- Three entry points: `xblock_asides.v1` → `RapidResponseAside`, plus `lms.djangoapp` and `cms.djangoapp` → `RapidResponseAppConfig` (registers `settings.common` for LMS, `settings.cms_settings` for CMS).
- `DJANGO_SETTINGS_MODULE = lms.envs.test` (see `setup.cfg`) — needs a full edx-platform test environment; no standalone settings module.
- `ENABLE_RAPID_RESPONSE_AUTHOR_VIEW` (CMS feature flag, default `False`): toggles a Studio "author view" affordance for enabling rapid response from the course outline (auto-publishes the problem if not already in draft when toggled).

## Notes
- Per the README, activating this plugin on an existing edX install also requires `ALLOW_ALL_ADVANCED_COMPONENTS: true` in LMS/CMS config, and a DB record for the `XBlockAsidesConfig` model (`/admin/lms_xblock/xblockasidesconfig/`) — and, if the author-view flag is on, also a `StudioConfig` record — none of which are created automatically by installing the package.
- A companion plugin, `ol-openedx-rapid-response-reports` (lives in a different repo/plugin, not this monorepo checkout), reads these same models to render CSV reports under the Instructor Dashboard's "Rapid Responses" tab. This xblock works fully standalone without it.
- Submission capture depends on the LMS tracking-event pipeline (`EVENT_TRACKING_BACKENDS`), not a direct handler call — `SubmissionRecorder.send()` silently ignores any event that isn't a single-answer `problem_check` for a multiple-choice response.
