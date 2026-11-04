"""
Tests for the git auto-export admin pages.
"""

from unittest import mock

from django.contrib.admin.sites import site
from django.test import RequestFactory, TestCase
from ol_openedx_git_auto_export.admin import (
    ContentGitExportLogAdmin,
    ContentGitRepositoryAdmin,
)
from ol_openedx_git_auto_export.models import (
    ContentGitExportLog,
    ContentGitRepository,
    ExportStatus,
)
from opaque_keys.edx.keys import CourseKey

COURSE_A = CourseKey.from_string("course-v1:org+a+run")
COURSE_B = CourseKey.from_string("course-v1:org+b+run")


class TestLastExportColumn(TestCase):
    """The repository list shows each row's newest export log entry."""

    def test_newest_row_per_content_key(self):
        for key in (COURSE_A, COURSE_B):
            ContentGitRepository.objects.create(content_key=key, git_url="a.git")
        ContentGitExportLog.objects.create(
            content_key=COURSE_A, status=ExportStatus.FAILED
        )
        newest = ContentGitExportLog.objects.create(
            content_key=COURSE_A, status=ExportStatus.SUCCESS
        )
        # Another key's newer row must not leak into COURSE_A's column.
        ContentGitExportLog.objects.create(
            content_key=COURSE_B, status=ExportStatus.NO_CHANGES
        )

        model_admin = ContentGitRepositoryAdmin(ContentGitRepository, site)
        rows = {
            row.content_key: row
            for row in model_admin.get_queryset(RequestFactory().get("/"))
        }

        assert (
            model_admin.last_export_status(rows[COURSE_A]) == ExportStatus.SUCCESS.label
        )
        assert model_admin.last_export_at(rows[COURSE_A]) == newest.created
        assert (
            model_admin.last_export_status(rows[COURSE_B])
            == ExportStatus.NO_CHANGES.label
        )

    def test_never_exported_shows_a_dash(self):
        ContentGitRepository.objects.create(content_key=COURSE_A, git_url="a.git")
        model_admin = ContentGitRepositoryAdmin(ContentGitRepository, site)
        row = model_admin.get_queryset(RequestFactory().get("/")).get()

        assert model_admin.last_export_status(row) == "-"
        assert model_admin.last_export_at(row) is None

    def test_a_status_this_release_does_not_know_is_shown_raw(self):
        """After a rollback, a newer release's status must not break the page."""
        ContentGitRepository.objects.create(content_key=COURSE_A, git_url="a.git")
        ContentGitExportLog.objects.create(content_key=COURSE_A, status="future_status")
        model_admin = ContentGitRepositoryAdmin(ContentGitRepository, site)
        row = model_admin.get_queryset(RequestFactory().get("/")).get()

        assert model_admin.last_export_status(row) == "future_status"


class TestExportLogAdminIsReadOnly(TestCase):
    """The export log is an audit trail: staff can view it, nothing more."""

    def test_no_add_change_or_delete(self):
        model_admin = ContentGitExportLogAdmin(ContentGitExportLog, site)
        request = RequestFactory().get("/")
        request.user = mock.Mock(is_superuser=True, is_active=True, is_staff=True)

        assert not model_admin.has_add_permission(request)
        assert not model_admin.has_change_permission(request)
        assert not model_admin.has_delete_permission(request)
