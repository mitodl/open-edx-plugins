# CLAUDE.md — ol_openedx_course_export

A Studio (CMS) Django app plugin that adds an API to export one or more courses as OLX
tarballs directly to an S3 bucket, instead of Open edX's default local-storage course
export. Export runs asynchronously via Celery, reusing edX's own
`CourseExportTask`/`create_export_tarball` machinery and `UserTaskStatus` for progress
tracking (which also triggers edX's built-in completion email).

## Key files
- `ol_openedx_course_export/views.py`: `CourseExportView` (DRF `GenericAPIView`,
  admin-only) — `POST` accepts `{"courses": [...]}` and kicks off one Celery task per
  course ID; `GET` (with `?task_id=`) checks a task's `UserTaskStatus`.
- `ol_openedx_course_export/tasks.py`: `task_upload_course_s3` — the Celery task
  (`base=CourseExportTask`) that builds the course tarball via `create_export_tarball`
  and uploads it via `S3Client`.
- `ol_openedx_course_export/s3_client.py`: `S3Client` — thin `boto3` wrapper around
  bucket upload and URL generation, keyed by `AWS_ACCESS_KEY_ID` /
  `AWS_SECRET_ACCESS_KEY` / `COURSE_IMPORT_EXPORT_BUCKET`.
- `ol_openedx_course_export/utils.py`: `is_bucket_configuration_valid`, file-name
  (`.tar.gz`) and public S3 URL helpers.
- `ol_openedx_course_export/urls.py`: routes `POST /` (export) and `GET /<course_id>/`
  (task status) under the plugin's URL prefix.
- `ol_openedx_course_export/app.py`: `CourseExportConfig` — registers URL
  (`^api/courses/v0/export/`) and settings for CMS only.
- `ol_openedx_course_export/settings/common.py` (no-op placeholder),
  `settings/production.py`.

## Entry points & settings
- `cms.djangoapp`: `ol_openedx_course_export.app:CourseExportConfig`, URL regex
  `^api/courses/v0/export/`, settings wired for common + production only (no devstack).
- Required settings (top-level in `cms.yml`/`private.py`): `AWS_ACCESS_KEY_ID`,
  `AWS_SECRET_ACCESS_KEY`, `COURSE_IMPORT_EXPORT_BUCKET`. Without a non-empty
  `COURSE_IMPORT_EXPORT_BUCKET`, POST requests 400 immediately
  (`is_bucket_configuration_valid`).
- API requires JWT authentication (DRF `IsAdminUser`); no waffle flag or course-level
  toggle — it's on wherever the plugin is installed.

## Notes
- No `tests/` directory in this plugin — relies on the repo-wide Tutor integration test
  flow.
- Per-course-ID failures inside the POST loop are caught individually and reported in
  `failed_uploads`, so a single bad course ID doesn't fail the whole batch (overall
  response is 400 if *any* course failed, 200 only if all succeeded).
- The upload URL returned to the client (`get_aws_file_url`) is constructed directly
  from `COURSE_IMPORT_EXPORT_BUCKET` + `s3.amazonaws.com`, independent of the actual
  upload's completion — it's returned immediately even though the export/upload happens
  asynchronously in Celery.
