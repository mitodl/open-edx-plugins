# CLAUDE.md — ol_openedx_auto_select_language

An LMS+CMS Django app that automatically switches the platform's UI language
to match the language configured on the course a user is viewing (e.g. a
Spanish-language course shows Spanish LMS chrome), while always forcing
English in Studio and in admin/instructor areas. Also adds an
`openedx-filters` pipeline step so video XBlocks default their transcript
language to the course language.

## Key files
- `ol_openedx_auto_select_language/middleware.py`:
  `CourseLanguageCookieMiddleware` (LMS) — on course-page responses, resolves
  the course's language via `CourseOverview`, converts it to BCP47, and sets
  it as the language cookie + user preference, redirecting to reapply; forces
  English for the authoring MFE origin and for
  `AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS`. `CourseLanguageCookieResetMiddleware`
  (CMS) — unconditionally resets the language cookie to English.
- `ol_openedx_auto_select_language/filters.py`: `AddDestLangForVideoBlock`, an
  `openedx-filters` `PipelineStep` on the XBlock render-started filter that
  sets `dest_lang` in a video block's student view context to the course
  language if a matching transcript exists.
- `ol_openedx_auto_select_language/views.py`: `CourseLanguageView` — public
  (throttled) API returning a course's language: `GET
  /course_language/<course_key>/`.
- `ol_openedx_auto_select_language/utils.py`: `LanguageCode` helper
  (`.to_bcp47()`) for normalizing edx-platform language codes.
- `ol_openedx_auto_select_language/settings/{common,lms,cms,filters,production}.py`:
  settings + middleware/filter registration, split by project type.

## Entry points & settings
- Registered for both `lms.djangoapp` and `cms.djangoapp` as
  `ol_openedx_auto_select_language.apps:OLOpenEdxAutoSelectLanguageConfig`.
  URLs mounted at the LMS root (empty namespace/regex) via `urls.py`. Settings
  hooks: `settings.lms` (common + production) and `settings.cms` (common).
- `settings.lms`/`settings.cms` each append their respective middleware to
  `MIDDLEWARE` and call `apply_common_settings`; `settings.filters` registers
  the video pipeline step into `OPEN_EDX_FILTERS_CONFIG` and must be
  re-applied from `production.py` too, since LMS production settings
  overwrite `OPEN_EDX_FILTERS_CONFIG` wholesale from deployment YAML.
- Key setting: `ENABLE_AUTO_LANGUAGE_SELECTION` (must be `True` for any
  middleware behavior to run — both middlewares no-op otherwise). Also:
  `AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS`, `COURSE_LANGUAGE_ANON_THROTTLE_RATE`
  / `COURSE_LANGUAGE_USER_THROTTLE_RATE` (API throttling), and
  `SHARED_COOKIE_DOMAIN` (must be set to share the cookie between LMS/CMS/MFEs).
- Tests: `DJANGO_SETTINGS_MODULE = lms.envs.test` (`setup.cfg`); has a real
  `tests/` suite (`test_filters.py`, `test_middleware.py`, `test_utils.py`,
  `test_views.py`).

## Notes
- MFE integration requires a custom Footer component (maintained in the
  separate `ol-infrastructure` repo, not here) plus
  `ENABLE_AUTO_LANGUAGE_SELECTION="true"` set per-MFE — this plugin only
  covers the Django-rendered LMS/CMS side.
- The middleware redirects the request when it changes the language cookie
  (to make the new language take effect immediately), so expect an extra
  redirect on first course-page load per session when the course language
  differs from the current cookie.
