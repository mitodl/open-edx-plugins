# CLAUDE.md — edx_username_changer

An LMS+CMS Django app that lets admins change a user's `username` through the
Django admin panel — normally a read-only field in edx-platform's admin. It
also propagates the rename to dependent systems (discussion forum, OAuth
social-auth records) via signal handlers so a changed username doesn't break
existing sessions/integrations.

## Key files
- `edx_username_changer/admin.py`: Re-registers `User` in Django admin with a
  custom `UserAdmin` that drops `username` from `get_readonly_fields` when the
  feature flag is on — this is what actually makes the field editable.
- `edx_username_changer/signals.py`: `user_pre_save_callback` (captures the
  old→new username diff via `get_changed_fields_dict`) and
  `user_post_save_callback` (fires the forum-sync task and updates
  social-auth) — wired declaratively in `apps.py`, not via `@receiver`.
- `edx_username_changer/tasks.py`: `task_update_username_in_forum` — Celery
  task that calls `forum.api.update_username` (Forum v2 API) after commit.
- `edx_username_changer/utils.py`: `update_user_social_auth_uid` (rewrites
  `UserSocialAuth.uid` when it matches the old username) and
  `get_enrolled_course_ids`.
- `edx_username_changer/exceptions.py`: `UpdateFailedException`.
- `edx_username_changer/settings/{common,devstack}.py`: toggle wiring for
  `FEATURES["ENABLE_EDX_USERNAME_CHANGER"]`.

## Entry points & settings
- Registered for both `lms.djangoapp` and `cms.djangoapp` as
  `edx_username_changer.apps:EdxUsernameChangerConfig`. No URLs — the app only
  wires two Django signal receivers on `django.contrib.auth.models.User`
  (`pre_save`/`post_save`) via the `PluginSignals` config in `apps.py`.
- Feature flag: `FEATURES["ENABLE_EDX_USERNAME_CHANGER"]` (default `False`,
  forced `False` in `settings/devstack.py`). Every signal handler and the
  admin override no-op unless this is `True` — the plugin does nothing by
  default even when installed.
- No `tests/` directory, `setup.cfg`, or pytest config in this plugin —
  no automated test suite currently exists.

## Notes
- **Forum v2 / MySQL backend only.** The forum-sync task assumes the
  MySQL-based Forum v2 backend; the MongoDB forum backend is explicitly
  unsupported and will create incorrect user records if usernames are changed
  while it's active. Verify the forum backend before enabling this plugin.
- The pre-save handler stashes changed fields on a transient
  `user._updated_fields` attribute for the post-save handler to consume, then
  deletes it — a same-transaction, in-memory handoff, not persisted anywhere.
- Forum sync failures (`ForumV2RequestError`) are logged and swallowed rather
  than raised, since the user may not exist in the forum yet.
