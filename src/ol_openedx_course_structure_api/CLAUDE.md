# CLAUDE.md — ol_openedx_course_structure_api

A small LMS Django app that exposes a read-only REST API returning the full JSON
representation of a course's block structure (categories, children, metadata,
and optionally inherited metadata). It wraps edx-platform's internal
`dump_course_structure` command logic (`dump_block`/`dump_module`) behind an
authenticated DRF view, giving external systems a way to introspect course
structure without shelling into the LMS.

## Key files
- `ol_openedx_course_structure_api/views.py`: `CourseStructureView` — the only
  endpoint. GET-only, superuser/admin-only, wraps `dump_block` from
  `lms.djangoapps.courseware.management.commands.dump_course_structure` (with a
  fallback import for older `dump_module` naming). Supports `inherited_metadata`
  and `inherited_metadata_default` query params.
- `ol_openedx_course_structure_api/urls.py`: mounts the view at
  `<course_id>/` under the plugin's URL prefix.
- `ol_openedx_course_structure_api/app.py`: `CourseStructureAPIConfig` — plugin
  wiring (URLs + settings).
- `ol_openedx_course_structure_api/settings/common.py`: `plugin_settings` hook,
  currently a no-op (no custom settings defined).

## Entry points & settings
- `[project.entry-points."lms.djangoapp"]` → `ol_openedx_course_structure_api.app:CourseStructureAPIConfig`.
  LMS-only; no CMS entry point.
- URL namespace: `PluginURLs.REGEX = "^api/course-structure/v0/"`, so the route
  is `<LMS_BASE>/api/course-structure/v0/<course_id>/`.
- No custom Django settings — `plugin_settings` in `settings/common.py` defines
  nothing beyond the docstring.
- No dedicated test settings/`setup.cfg` pytest config and no `tests/` directory
  in this plugin — it currently has no automated test suite.

## Notes
- Auth is `IsAdminUser` only (JWT, Bearer, or Session auth accepted) — this is
  an admin/service-to-service API, not learner-facing.
- Depends on internal edx-platform command internals (`dump_course_structure`),
  so it's coupled to that command's presence/signature across releases; the
  try/except import handles the `dump_module` → `dump_block` rename.
- Returns 404 for both invalid course IDs and courses not found in the
  modulestore.
