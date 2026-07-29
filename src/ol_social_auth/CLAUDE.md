# CLAUDE.md — ol_social_auth

An LMS-only Django app plugin implementing an MIT-specific OAuth2 social-auth
backend (`ol-oauth2`) built on `social-auth-core`'s `BaseOAuth2`, so users
created in an MIT application (e.g. xPro, MITx Online) get a corresponding
edX account transparently via SSO. It also registers a scheduled Celery task
that cleans up expired OAuth2 tokens.

## Key files
- `ol_social_auth/backends.py`: `OLOAuth2` backend — resolves authorization/token/userinfo endpoints either from an OpenID discovery document (`DISCOVERY_URL` setting) or from explicit `AUTHORIZATION_URL`/`ACCESS_TOKEN_URL`/`API_ROOT` settings (used when there's no discovery URL, e.g. xPro); maps the MIT app's user payload to edX user details (`username`, `email`, `name`).
- `ol_social_auth/tasks.py`: `ol_clear_expired_tokens` Celery task — wraps django-oauth-toolkit's `clear_expired()`, temporarily silencing `oauth2_provider`'s debug logging (its debug logs lack a `userid` field the platform's custom log formatter expects).
- `ol_social_auth/settings/common.py`: `plugin_settings()` — sets `OAUTH2_PROVIDER["REFRESH_TOKEN_EXPIRE_SECONDS"]` to 30 days (down from edx-platform's 90-day default) and registers the cleanup task on `CELERYBEAT_SCHEDULE`.
- `ol_social_auth/apps.py`: `OLSocialAuthConfig` — registers `settings.common`/`settings.production` for `lms.djangoapp`.
- `tests/backends_test.py`, `tests/tasks_test.py`: unit tests.

## Entry points & settings
- `lms.djangoapp` entry point only. `plugin_settings` runs automatically; no manual `INSTALLED_APPS`/`AUTHENTICATION_BACKENDS` wiring documented here beyond what the plugin itself sets.
- `DJANGO_SETTINGS_MODULE = lms.envs.test` (see `setup.cfg`) — like most plugins in this repo, tests need a full edx-platform environment, not a standalone Django settings module.
- Backend-specific settings (read via `self.setting(...)`, i.e. `SOCIAL_AUTH_OL_OAUTH2_*` in edx-platform convention): `DISCOVERY_URL` (optional — if unset, falls back to explicit URLs below), `AUTHORIZATION_URL`, `ACCESS_TOKEN_URL`, `API_ROOT`.
- Celery Beat schedule entry `ol_clear_expired_tokens` runs Monday 9:00 AM server time by default; operators can override it by setting a different `CELERYBEAT_SCHEDULE["ol_clear_expired_tokens"]` entry.

## Notes
- Real integration (devstack/Tutor) requires additional handbook-documented config beyond this plugin's own settings — see the links in `README.rst` under "Configurations".
- If deploying against a database with a large backlog of already-expired tokens, the README recommends running django-oauth-toolkit's `clear_expired` management command manually once before relying on the scheduled task, to avoid an expensive first run.
- `_get_metadata()` caches the discovery document on the backend instance (`_discovery_doc`) to avoid refetching per request.
