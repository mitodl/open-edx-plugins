# CLAUDE.md — ol_openedx_chat

An XBlock **aside** (not a standalone block) that adds MIT Open Learning's "AskTIM" AI chat/VideoGPT to existing video and problem blocks, without modifying those blocks directly. It renders a chat drawer button in the LMS and a config checkbox in Studio, and calls out to the MIT Learn AI API (`MIT_LEARN_AI_API_URL`) for chat and to `MIT_LEARN_SUMMARY_FLASHCARD_URL` for video transcript summaries/flashcards.

## Key files
- `ol_openedx_chat/block.py`: `OLChatAside` — the `XBlockAside` itself; student/author views, `should_apply_to_block` gating logic, `update_chat_config` and `track_user_events` XBlock handlers.
- `ol_openedx_chat/compat.py`: defines the `ol_openedx_chat.ol_openedx_chat_enabled` `CourseWaffleFlag` (isolates the waffle-flag import from core platform).
- `ol_openedx_chat/utils.py`: course lookup, per-course/per-block-type enable checks via `other_course_settings`, transcript asset ID resolution, language-code (Django ↔ BCP47) conversion.
- `ol_openedx_chat/constants.py`: block categories the aside applies to (`video`, `problem`), MIT AI chat URL path suffixes, mapping from block type to the "Other Course Settings" flag name.
- `ol_openedx_chat/apps.py`: `OLOpenedxChatConfig` — registers plugin settings for both LMS and CMS.
- `ol_openedx_chat/settings/common.py`, `settings/devstack.py`: pull `MIT_LEARN_AI_API_URL`, `MIT_LEARN_API_BASE_URL`, `MIT_LEARN_SUMMARY_FLASHCARD_URL` from `ENV_TOKENS`.
- `ol_openedx_chat/static/{html,css,js}/`: student/studio view templates and the aside's front-end (drawer init calls into the `@mitodl/smoot-design` bundle loaded by the learning MFE — see README step 3-4).
- `tests/test_aside.py`, `tests/test_utils.py`: pytest suite (`DJANGO_SETTINGS_MODULE = lms.envs.test`, see `setup.cfg`).

## Entry points & settings
- `xblock_asides.v1`: `ol_openedx_chat = ol_openedx_chat.block:OLChatAside`.
- `lms.djangoapp` / `cms.djangoapp`: `ol_openedx_chat.apps:OLOpenedxChatConfig`, both wired to `settings.common` / `settings.devstack`.
- Required settings (from `ENV_TOKENS`, top-level in `lms.yml`/`private.py`): `MIT_LEARN_AI_API_URL`, `MIT_LEARN_API_BASE_URL`, `MIT_LEARN_SUMMARY_FLASHCARD_URL`.
- Feature gating is two-layered: the `ol_openedx_chat.ol_openedx_chat_enabled` course waffle flag (default off) must be enabled for the course, **and** the course's "Other Course Settings" JSON must set `OL_OPENEDX_CHAT_VIDEO_BLOCK_ENABLED` / `OL_OPENEDX_CHAT_PROBLEM_BLOCK_ENABLED`. Also requires `FEATURES["ENABLE_OTHER_COURSE_SETTINGS"] = True` and `XBlockAsidesConfig`/`StudioConfig` DB records to activate at all.

## Notes
- During course import, `should_apply_to_block` short-circuits to a block-type-only check (skips waffle flag / course settings lookups) because course context isn't available yet — see the `XMLImportingModuleStoreRuntime` branch in `block.py`.
- The LMS front end depends on a separately-installed `@mitodl/smoot-design` JS bundle in frontend-app-learning (`aiDrawerManager.es.js`) — this plugin only supplies the aside/handlers and drawer payload, not that bundle.
- Translations do NOT use this repo's Transifex/Atlas flow (no `conf/locale/config.yaml` or Makefile) — `.po` files live in a separate translations repo and are synced via `sync_and_translate_language`, then pulled into edx-platform via `make pull_translations`. See README for the full rationale.
- `get_checkpoint_and_thread_id` parses an HTML comment embedded in the chat response body (`<!-- {"checkpoint_pk": ..., "thread_id": ...} -->`) — a fragile but intentional contract with the MIT Learn AI backend.
