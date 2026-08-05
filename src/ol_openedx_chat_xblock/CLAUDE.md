# CLAUDE.md — ol_openedx_chat_xblock

A standalone XBlock (added via "Advanced module list", not an aside) that embeds MIT
Open Learning's AI chat ("AskTIM") directly into a course unit. It supports two modes —
"Syllabus Chat" (course-content Q&A) and "Tutor Chat" (problem-set assistance) —
proxying requests server-side to the MIT Learn AI API. Distinct from and unrelated in
code to `ol_openedx_chat` (the video/problem aside); this one is its own block students
explicitly add to a unit.

## Key files
- `ol_openedx_chat_xblock/block.py`: `OLChatXBlock` (`XBlock` +
  `StudioEditableXBlockMixin`) — fields (`course_id`, `is_tutor_xblock`,
  LTI-auto-generated `learn_readable_course_id`), `ol_chat` and `ol_chat_rate` handlers
  that proxy to the MIT Learn AI chat/rating APIs, cookie-based chat-thread session
  tracking, Canvas LTI course-ID auto-generation.
- `ol_openedx_chat_xblock/filters.py`: `DisableMathJaxForOLChatBlock`, an Open edX
  Filters `PipelineStep` that disables MathJax rendering on units containing this block.
- `ol_openedx_chat_xblock/constants.py`: cookie names, initial chat messages,
  "Tutor"/"Syllabus" labels, `+canvas` course-ID suffix used for tutor-mode lookups.
- `ol_openedx_chat_xblock/apps.py`: `OLOpenedxChatXBlockConfig` — registers plugin
  settings for LMS and CMS (common/production/devstack).
- `ol_openedx_chat_xblock/settings/common.py`, `settings/production.py`,
  `settings/filters.py`: pull `MIT_LEARN_AI_XBLOCK_*` settings from `ENV_TOKENS`;
  `filters.py` has `register_chat_xblock_filter()`, called from both common and
  production because production settings overwrite `OPEN_EDX_FILTERS_CONFIG` wholesale.
- `ol_openedx_chat_xblock/static/{html,css,js}/`: student/studio view templates and the
  front-end chat widget JS.
- `tests/test_block.py`, `tests/test_filters.py`: pytest suite
  (`DJANGO_SETTINGS_MODULE = lms.envs.test`, see `setup.cfg`).

## Entry points & settings
- `xblock.v1`: `ol_openedx_chat_xblock = ol_openedx_chat_xblock.block:OLChatXBlock`.
- `lms.djangoapp` / `cms.djangoapp`:
  `ol_openedx_chat_xblock.apps:OLOpenedxChatXBlockConfig`.
- Settings from `ENV_TOKENS`: `MIT_LEARN_AI_XBLOCK_CHAT_API_TOKEN` (required),
  `MIT_LEARN_AI_XBLOCK_CHAT_API_URL` (required for Syllabus Chat),
  `MIT_LEARN_AI_XBLOCK_TUTOR_CHAT_API_URL` + `MIT_LEARN_AI_XBLOCK_PROBLEM_SET_LIST_URL`
  (required for Tutor Chat), `MIT_LEARN_AI_XBLOCK_CHAT_RATING_URL` (for the rating
  handler).
- Activation requires adding `ol_openedx_chat_xblock` to the course's Studio "Advanced
  module list", then adding the block via the Advanced component picker.

## Notes
- Course ID resolution priority: explicit `course_id` field on the block >
  `learn_readable_course_id` auto-generated from a Canvas LTI launch (`custom_course_id`
  + `context_label` request params) > error. This xBlock is designed to be embedded via
  LTI from Canvas, not just native Open edX courses.
- Like the sibling `ol_openedx_chat` plugin, chat responses embed thread/checkpoint
  metadata as an HTML comment (`<!-- {"checkpoint_pk": ..., "thread_id": ...} -->`) that
  `get_checkpoint_and_thread_id` parses; the rating handler instead extracts
  thread/checkpoint IDs from the handler URL suffix.
- Uses `requests` (synchronous, 60s timeout) to call the external MIT Learn AI service
  directly from the handler — no async/celery involved, so a slow upstream call blocks
  the request.
