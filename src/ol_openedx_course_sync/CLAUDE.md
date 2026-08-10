# CLAUDE.md — ol_openedx_course_sync

A CMS/LMS Django app that keeps course reruns (and other designated target
courses) in sync with a source/parent course. When a source course is
published, or its discussion configuration changes, the plugin propagates
content, assets, and discussion settings to all mapped target courses via
Celery tasks. It also ships two management commands: one to migrate legacy
(v1) `library_content` blocks to v2 library item banks, and one to reset/rescore
learner problem attempts across a source course and its synced targets.

## Key files
- `ol_openedx_course_sync/models.py`: `CourseSyncOrganization` (source orgs
  eligible for sync) and `CourseSyncMapping` (source → target course pairs,
  with validation preventing cycles/conflicts).
- `ol_openedx_course_sync/signals.py`: listens for
  `xmodule.modulestore.django.COURSE_PUBLISHED` (triggers content + asset
  sync), `CourseRerunState` post_save (auto-creates a `CourseSyncMapping` when
  a rerun succeeds, for orgs registered as sync sources), and
  `DiscussionsConfiguration`/`CourseDiscussionSettings` post_save (syncs
  discussion settings).
- `ol_openedx_course_sync/tasks.py`: Celery tasks doing the actual sync work
  (`async_course_sync`, `async_course_assets_sync`,
  `async_discussions_configuration_sync`).
- `ol_openedx_course_sync/utils.py`: `get_syncable_course_mappings` and other
  helpers used by signals/tasks.
- `ol_openedx_course_sync/management/commands/migrate_legacy_library_blocks_to_item_bank.py`:
  `migrate_legacy_library_blocks_to_item_bank` CMS command (v1 → v2 library
  migration, supports `--course-ids`/`--all-source-courses`/`--persist-publish-state`).
- `ol_openedx_course_sync/management/commands/sync_problem_actions.py`:
  `sync_problem_actions` LMS command (`reset_attempts`/`rescore` across source +
  synced target courses).
- `ol_openedx_course_sync/admin.py`: Django admin registration for the two
  models (primary way operators configure sync).
- `ol_openedx_course_sync/migrations/0001_initial.py`: only migration so far.
- `tests/`: covers models, signals, tasks, utils, and the library-migration
  command.

## Entry points & settings
- Registered under both `[project.entry-points."cms.djangoapp"]` and
  `"lms.djangoapp"` → `ol_openedx_course_sync.apps:OLOpenEdxCourseSyncConfig`.
  CMS install is required for sync itself; LMS install is required for the
  `sync_problem_actions` command.
- Signal receiver wiring lives in `apps.py`'s `plugin_app` dict (CMS only) —
  not in `signals.py` via `@receiver` for the publish signal (it's registered
  declaratively), though the discussions/rerun-state receivers do use
  `@receiver` decorators directly in `signals.py`.
- Required setting: `OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME` (CMS) —
  all sync operations and the library migration run on behalf of this user.
  Without it, syncing and the migration command will not work correctly. Set
  via `ENV_TOKENS` (e.g. `tutor config save --set
  OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME={USERNAME}`).
- Test settings module: `lms.envs.test` (per `setup.cfg`).

## Notes
- Sync only activates for organizations explicitly registered as active in
  `CourseSyncOrganization` — installing the plugin alone does nothing until an
  org and at least one `CourseSyncMapping` are configured (via Django admin).
- A course can't be both a source and a target at once — `CourseSyncMapping`
  validation (`clean()`) rejects conflicting/cyclic mappings.
- Supports Open edX releases from Sumac onward (per README).
