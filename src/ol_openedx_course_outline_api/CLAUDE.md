# CLAUDE.md — ol_openedx_course_outline_api

An LMS Django app plugin exposing a read-only, admin-only API
(`GET /api/ol-course-outline/v0/<course_id>/`) that returns a per-chapter course outline
summary — title, effort estimate, and content-type counts
(videos/readings/problems/assignments/app_items) — intended to power the MIT Learn
product page's course-module listing.

## Key files
- `ol_openedx_course_outline_api/views.py`: `CourseOutlineView` (DRF `APIView`,
  `IsAdminUser`) — looks up the course, builds/returns a cached response, otherwise
  calls the platform Blocks API (`get_blocks`) with specific `requested_fields`
  (including `EffortEstimationTransformer` fields) and delegates summarization to
  `utils.build_modules_from_blocks`.
- `ol_openedx_course_outline_api/utils.py`: pure functions that walk the Blocks API tree
  per chapter — `build_modules_from_blocks`, per-type counters
  (`count_blocks_by_type_under_chapter`, `count_assignments_under_chapter`,
  `count_app_items_under_chapter`), staff-only/hide-from-toc filtering
  (`iter_descendant_ids` prunes both). This is where to look/change if the response
  shape or counting rules need adjusting.
- `ol_openedx_course_outline_api/constants.py`: block-type groupings,
  `NOT_GRADED_FORMAT`, and `COURSE_OUTLINE_CACHE_SCHEMA_VERSION` — **bump this constant
  whenever the response shape or computation logic changes**, since it's embedded in the
  cache key.
- `ol_openedx_course_outline_api/urls.py`: routes `GET /<course_id>/` to
  `CourseOutlineView`.
- `ol_openedx_course_outline_api/app.py`: `CourseOutlineAPIConfig` — registers URL
  (`^api/ol-course-outline/v0/`) and settings for LMS only.
- `ol_openedx_course_outline_api/settings/common.py`, `settings/production.py`: cache
  prefix/timeout settings.

## Entry points & settings
- `lms.djangoapp`: `ol_openedx_course_outline_api.app:CourseOutlineAPIConfig`, URL regex
  `^api/ol-course-outline/v0/`, settings wired for common + production only (no
  devstack).
- Optional settings: `OL_COURSE_OUTLINE_API_CACHE_KEY_PREFIX` (default
  `ol_course_outline_api:outline:v0:`), `OL_COURSE_OUTLINE_API_CACHE_TIMEOUT_SECONDS`
  (default 1 week). Both fall back to sane defaults if unset, so the plugin works out of
  the box.
- Auth: JWT (`JwtAuthentication`), bearer, or session auth; `IsAdminUser` permission —
  not accessible to regular learners/staff-only-course-team members.

## Notes
- No `tests/` directory in this plugin — relies on the repo-wide Tutor integration test
  flow.
- **Caching**: full JSON response is cached under
  `<prefix>s<schema_version>:<course_key>:<content_version>`. `content_version` is
  `course.course_version` (or `"na"` if absent); publishing a course that changes
  `course_version` naturally invalidates old entries — there's no explicit
  cache-bust/signal wiring, it's purely key-based.
- `generated_at` is fixed at cache-write time, so cached responses return a
  stale-looking timestamp until the cache entry expires or the course is republished.
- Counting logic treats a sequential as an "assignment" if `graded=True` OR it has a
  non-empty, non-`notgraded` `format` — this intentionally covers Studio's "linked to
  assignment type" state even when `graded` itself is False.
