# CLAUDE.md — ol_openedx_feedback

An LMS-only plugin that adds a small "Send feedback" trigger to applicable
leaf blocks (problem, video, html, etc.) via an `XBlockAside`. Clicking it
posts an `ol-feedback::drawer-open` message (with course/block context) to the
parent window; the Learning MFE listens for that message and opens a feedback
drawer that submits directly to the external **mit-learn** service. This
plugin persists nothing in edx-platform and exposes no REST API or models —
it is purely a trigger/messaging layer.

## Key files
- `ol_openedx_feedback/block.py`: `FeedbackAside` (`XBlockAside`) — the whole
  feature. `student_view_aside` renders the trigger only for authenticated
  learners (never in Studio author/preview, never for anonymous users);
  `should_apply_to_block` gates on the `feedback_enabled` course waffle flag
  plus `is_aside_applicable_to_block`, with a special case to skip the
  waffle-flag lookup during XML course import (no resolvable course context
  at that point).
- `ol_openedx_feedback/utils.py`: `is_aside_applicable_to_block` — excludes
  structural/container block types (course/chapter/sequential/vertical by
  default, or `OL_OPENEDX_FEEDBACK_EXCLUDED_BLOCK_TYPES` if overridden).
- `ol_openedx_feedback/compat.py`: isolates the `CourseWaffleFlag` import from
  edx-platform; defines the `ol_openedx_feedback.feedback_enabled` toggle
  (`get_feedback_enabled_flag`).
- `ol_openedx_feedback/constants.py`: `DEFAULT_EXCLUDED_BLOCK_TYPES`.
- `ol_openedx_feedback/static/{html,css,js}/`: the trigger's template
  (`student_view.html`), styling (`feedback.css`), and
  `FeedbackAsideInit`/postMessage JS (`feedback.js`).
- `ol_openedx_feedback/settings/common.py`: `plugin_settings` — populates
  `OL_OPENEDX_FEEDBACK_EXCLUDED_BLOCK_TYPES` from `ENV_TOKENS` or the default.
- `tests/test_aside.py`, `tests/test_utils.py`: aside rendering/gating and
  utility logic.

## Entry points & settings
- `[project.entry-points."xblock_asides.v1"]` →
  `ol_openedx_feedback.block:FeedbackAside` — this is what actually attaches
  the aside to blocks; no manual `INSTALLED_APPS`/XBlock registration needed.
- `[project.entry-points."lms.djangoapp"]` →
  `ol_openedx_feedback.apps:OLOpenedxFeedbackConfig` — LMS only (no CMS entry
  point at all; the trigger is learner-facing only).
- Setting: `OL_OPENEDX_FEEDBACK_EXCLUDED_BLOCK_TYPES` (default `{course,
  chapter, sequential, vertical}`) — override via `ENV_TOKENS`/`lms.yml` to
  additionally exclude block types (e.g. `html`).
- Test settings module: `lms.envs.test` (per `setup.cfg`).

## Notes
- Two independent activation gates must both be satisfied for the trigger to
  render anywhere: (1) XBlock asides must be turned on globally in LMS admin
  at `/admin/lms_xblock/xblockasidesconfig/` (with the target block types not
  listed in that config's own "Disabled blocks" field, which defaults to
  `about course_info static_tab`), and (2) the `ol_openedx_feedback.feedback_enabled`
  course waffle flag must be enabled per-course (default off). Installing the
  package alone does nothing.
- No models, migrations, REST API, or CMS install — everything happens
  client-side via `postMessage` to the Learning MFE, which owns the actual
  submission to mit-learn.
