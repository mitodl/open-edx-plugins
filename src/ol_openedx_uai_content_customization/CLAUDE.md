# CLAUDE.md — ol_openedx_uai_content_customization

A CMS-only Django app plugin that ships a management command,
`generate_uai_course_versions`, to bulk-generate industry- and length-specific
"UAI" course variants from a single processed-videos CSV. For each unique
`(course_key, industry, duration)` row group it clones the source course via
direct modulestore APIs, strips its sections, and rebuilds an `Introduction`
(optional) + `Lectures` content tree from the CSV data, preserving all
original course settings (grading, certificates, pacing, advanced settings).

## Key files
- `ol_openedx_uai_content_customization/management/commands/generate_uai_course_versions.py`: the command itself — validates source course keys up front (fail-fast), groups CSV rows, clones/creates courses, builds content blocks, publishes.
- `ol_openedx_uai_content_customization/csv_utils.py`: CSV parsing, course-key generation (`build_new_course_key`), industry/duration code mapping, course-intro resolution with a 3-level fallback (exact → industry → "Original" industry).
- `ol_openedx_uai_content_customization/modulestore_utils.py`: thin modulestore wrappers (`clone_course_in_modulestore`, `delete_course_sections`, `create_content_block`, `save_video_block_with_edx_video_id`) kept separate so the command stays thin and mockable in tests.
- `ol_openedx_uai_content_customization/constants.py`: industry codes (`Healthcare→HC`, `Finance→F`, `Energy→E`, `Original→""`), duration codes (`short→S`, `long→F`), required CSV columns, block-type/display-name constants.
- `ol_openedx_uai_content_customization/apps.py`: registers CMS-only settings (`settings.common` / `settings.production`), both currently no-ops.
- `tests/test_csv_utils.py`, `tests/test_generate_uai_course_versions.py`: unit tests.

## Entry points & settings
- `cms.djangoapp` entry point only (`OLOpenEdxUaiContentCustomizationConfig`) — this plugin does not install into the LMS.
- No feature flags or `ENV_TOKENS` config — behavior is entirely driven by CLI args to the management command: `--processed-videos-csv` (required), `--username` (default `studio_worker`), `--dry-run`.
- Required CSV columns: `course_key`, `industry`, `duration`, `video_file_name`, `video_title`, `module_name`, `course_intro`, `edx_video_id`. Column names are matched case-insensitively.

## Notes
- **As of v0.2.0 this is a single-CSV workflow** (see `CHANGELOG.rst`). The older two-CSV design (a separate edX-videos-export CSV cross-referenced by file name) was collapsed into one CSV that carries `edx_video_id` directly — don't reintroduce a second `--edx-videos-csv` argument or file-name-based video matching.
- Course creation is **not atomic**: MongoDB writes aren't covered by Django transactions. A failed run leaves partially-created courses in place; reruns skip already-created course keys with a `DuplicateCourseError` warning rather than erroring out.
- The command validates all source course keys against the live modulestore before any writes, and reports every missing/invalid key in one error rather than failing on the first.
- Course key format: `course-v1:ORG+NUMBER.<DURATION>[.<INDUSTRY>]+RUN` — no industry code segment for "Original".
- Video rows with no `edx_video_id` are skipped (logged as unmapped) rather than failing the whole run.
