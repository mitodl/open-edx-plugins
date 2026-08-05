# CLAUDE.md — ol_openedx_events_handler

A generic LMS/CMS Django app that centralizes Open edX signal/event handlers
for MIT Open Learning, so new reactions to platform events don't each need
their own plugin. It currently reacts to two events by POSTing webhooks to
external MIT systems: course access role additions (to auto-enroll
staff/instructors as auditors) and passing-grade events (to trigger
certificate creation).

## Key files
- `ol_openedx_events_handler/handlers/course_access_role.py`:
  `handle_course_access_role_added` — reacts to the openedx-events
  `COURSE_ACCESS_ROLE_ADDED` signal (LMS and CMS). Filters by
  `ENROLLMENT_COURSE_ACCESS_ROLES`, resolves the user's email, and dispatches
  the `notify_course_access_role_addition` Celery task.
- `ol_openedx_events_handler/receivers/certificate_passing_receiver.py`:
  `listen_for_passing_grade` — reacts to the legacy Django signal
  `COURSE_GRADE_NOW_PASSED` (LMS only). Checks certificate eligibility
  (`_is_eligible_for_certificate`: active enrollment, eligible mode, self-paced
  or early-no-info display behavior) before dispatching
  `create_certificate_for_passing_grade`.
- `ol_openedx_events_handler/tasks.py`: the two Celery tasks that actually POST
  to the configured webhook URLs, with `requests`-exception autoretry
  (2 retries, exponential backoff).
- `ol_openedx_events_handler/utils.py`: `validate_enrollment_webhook` /
  `validate_certificate_webhook` — plain settings-truthiness checks (via
  `getattr`) that return `False` and log a warning when the relevant
  URL/token setting is missing. Called from `handlers/course_access_role.py`
  and `receivers/certificate_passing_receiver.py` respectively, before task
  dispatch — not from `tasks.py` itself.
- `ol_openedx_events_handler/settings/common.py`: `plugin_settings` — declares
  all webhook-related settings with `None`/default-role-list defaults.
- `ol_openedx_events_handler/apps.py`: wires up receivers per project type —
  CMS only gets the course-access-role receiver; LMS gets both.
- `tests/`: one test module per handler/receiver/task plus `test_utils.py`.

## Entry points & settings
- Registered under both `[project.entry-points."lms.djangoapp"]` and
  `"cms.djangoapp"` → `ol_openedx_events_handler.apps:OlOpenedxEventsHandlerConfig`.
  Install required in both LMS and Studio (CMS).
- Signal wiring is declarative in `apps.py`'s `plugin_app[PluginSignals.CONFIG]`
  (not `@receiver` decorators), pointing at
  `openedx_events.learning.signals.COURSE_ACCESS_ROLE_ADDED` and
  `openedx.core.djangoapps.signals.signals.COURSE_GRADE_NOW_PASSED`.
- Settings (set via `ENV_TOKENS`/`lms.yml`/`cms.yml`/`private.py`, top level):
  - `ENROLLMENT_WEBHOOK_URL`, `ENROLLMENT_WEBHOOK_ACCESS_TOKEN` — required for
    the enrollment webhook to actually fire.
  - `ENROLLMENT_COURSE_ACCESS_ROLES` (default `["instructor", "staff"]`) —
    which roles trigger the enrollment webhook.
  - `CERTIFICATE_WEBHOOK_URL`, `CERTIFICATE_WEBHOOK_ACCESS_TOKEN` — required
    for the certificate webhook; the task explicitly no-ops (logs an error and
    returns) if either is missing.
- Test settings module: `lms.envs.test` (per `setup.cfg`).

## Notes
- Both webhooks are no-ops until fully configured — installing the plugin
  without setting URLs/tokens means events are received but nothing is sent
  (validated via `validate_*_webhook` before dispatch). `tasks.py`'s
  `create_certificate_for_passing_grade` has its own separate inline
  URL/token check as a second layer of defense; `notify_course_access_role_addition`
  relies solely on the caller having validated first.
- This is meant to be the single home for *all* MIT OL signal/event reactions
  going forward — when adding a new event reaction, prefer extending this
  plugin (new handler + task + settings) over creating a new one, per the
  README's stated purpose.
- Recent history: Celery task autodiscovery required flattening a `tasks/`
  package into a single `tasks.py` (see CHANGELOG 0.2.1) — keep tasks in that
  single module rather than reintroducing a package.
