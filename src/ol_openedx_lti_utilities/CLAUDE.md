# CLAUDE.md — ol_openedx_lti_utilities

A small LMS Django app that exposes a single maintenance API endpoint for repairing
LTI-created user accounts that ended up in a bad auth state (username permanently pinned
to their `lti_user_id`). It is a single-view REST endpoint, not a hook into the LTI
launch flow itself.

## Key files
- `ol_openedx_lti_utilities/views.py`: `LtiUserFixView` (DRF `APIView`, POST only) —
  given an `email`, finds the matching `LtiUser` row, verifies the account is actually
  LTI-created (username == `lti_user_id`), rewrites the user's email to a placeholder
  domain (`lti_example.com`), deletes `UserSocialAuth` rows and the `LtiUser` mapping,
  then submits the account for retirement/deactivation.
- `ol_openedx_lti_utilities/urls.py`: mounts the view only when
  `settings.FEATURES["ENABLE_LTI_PROVIDER"]` is truthy; otherwise `urlpatterns` is empty
  and the route doesn't exist.
- `ol_openedx_lti_utilities/app.py`: `LTIUtilitiesConfig` — registers the URL regex
  `^api/lti-user-fix/` under LMS.

## Entry points & settings
- `lms.djangoapp` entry point only (`LTIUtilitiesConfig`); no CMS component.
- No plugin-specific settings module — the endpoint is gated purely by the platform's
  existing `FEATURES["ENABLE_LTI_PROVIDER"]` flag (if unset/false, the URL is never
  registered).
- Auth on the view: `JwtAuthentication`, `BearerAuthenticationAllowInactiveUser`,
  `SessionAuthenticationAllowInactiveUser`, permission
  `JWT_RESTRICTED_APPLICATION_OR_USER_ACCESS` — same pattern as `CourseModesMixin`
  elsewhere in the platform.
- Tests run against edx-platform settings (`DJANGO_SETTINGS_MODULE = lms.envs.test` in
  `setup.cfg`), i.e. via the Tutor integration flow, not standalone.

## Notes
- Endpoint: `POST <LMS_BASE>/lti-user-fix/` with JSON body `{"email": "..."}`. Returns
  404 if no matching `LtiUser`, 400 if the user isn't actually LTI-created (username !=
  lti_user_id) or `email` is missing, 200 on success.
- This is a destructive/irreversible operation on the target account (deletes
  social-auth + LTI mapping and initiates retirement) — intended as an admin/ops
  remediation tool, not a self-service endpoint.
- `PLACEHOLDER_EMAIL_DOMAIN = "lti_example.com"` is hardcoded in `views.py`; changing it
  requires a code change, not a setting.
- CHANGELOG.rst currently has no released entries (still at the "Unreleased" template).
