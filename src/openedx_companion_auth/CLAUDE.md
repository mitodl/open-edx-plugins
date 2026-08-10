# CLAUDE.md — openedx_companion_auth

An LMS-only Django app plugin that redirects anonymous edx-platform users to
an MIT application's login flow instead of edx-platform's own login page,
via a request middleware. It's the companion to `ol_social_auth`'s OAuth2
backend: this plugin forces users toward SSO login; `ol_social_auth` handles
the resulting account linking.

## Key files
- `openedx_companion_auth/middleware.py`: `RedirectAnonymousUsersToLoginMiddleware` — on
  each request, if `MITX_REDIRECT_ENABLED` is `True` and the user is anonymous,
  redirects to `MITX_REDIRECT_LOGIN_URL` (appending the original URL as a `next` query
  param), unless the path matches `MITX_REDIRECT_ALLOW_RE_LIST` (allow-list, checked
  first) or matches `MITX_REDIRECT_DENY_RE_LIST` (deny-list).
- `openedx_companion_auth/settings/common.py`: `plugin_settings()` — sets the default
  config values and **appends the middleware to `settings.MIDDLEWARE`**.
- `openedx_companion_auth/apps.py`: `MITxCoreConfig` — registers
  `settings.common`/`settings.production` for `lms.djangoapp`.
- `openedx_companion_auth/urls.py`: intentionally empty (`urlpatterns = []`); no URLs of
  its own.
- `tests/middleware_test.py`: unit tests for the middleware.

## Entry points & settings
- `lms.djangoapp` entry point only (`MITxCoreConfig`). `plugin_settings` both sets
  defaults and mutates `settings.MIDDLEWARE` — no manual settings/middleware wiring
  needed.
- Defaults set by `plugin_settings()`: `MITX_REDIRECT_ENABLED = True`,
  `MITX_REDIRECT_LOGIN_URL = "/auth/login/ol-oauth2/?auth_entry=login"` (points at
  `ol_social_auth`'s backend by convention),
  `MITX_REDIRECT_ALLOW_RE_LIST = [r"^/(admin|auth|login|logout|register|api|oauth2|user_api)"]`,
  `MITX_REDIRECT_DENY_RE_LIST = []`.
- No standalone `DJANGO_SETTINGS_MODULE` for pytest is configured in
  `pyproject.toml`/`setup.cfg`; `openedx_companion_auth/settings/test.py` exists and
  builds a minimal settings object (sqlite DB, `ROOT_URLCONF` pointed at this plugin's
  empty `urls.py`) for use when tests are run against it directly.

## Notes
- **This plugin is active by default, not a no-op until configured** —
  `MITX_REDIRECT_ENABLED` defaults to `True`, so simply installing it starts redirecting
  anonymous users. Deployments that don't want the redirect must explicitly override
  `MITX_REDIRECT_ENABLED = False` (or adjust the allow/deny lists).
- Allow-list is checked before deny-list: if `MITX_REDIRECT_ALLOW_RE_LIST` is set and
  the path doesn't match anything in it, the user is redirected regardless of the deny
  list.
- Pairs with `ol_social_auth` (the `ol-oauth2` backend referenced in the default login
  URL) but has no code dependency on it — the two plugins are wired together only
  through shared settings conventions.
