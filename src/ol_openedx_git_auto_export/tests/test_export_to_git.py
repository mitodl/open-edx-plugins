"""
Tests for the export_to_git command and the matching admin action.
"""

from contextlib import nullcontext
from io import StringIO
from unittest import mock

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Permission, User
from django.core.management import CommandError, call_command
from django.test import RequestFactory, TestCase
from ol_openedx_git_auto_export.admin import ContentGitRepositoryAdmin
from ol_openedx_git_auto_export.exceptions import ContentNotFoundError
from ol_openedx_git_auto_export.models import ContentGitRepository
from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.locator import LibraryLocator, LibraryLocatorV2

ENABLED_COURSE = CourseKey.from_string("course-v1:MITx+Enabled+1T2026")
ENABLED_LIBRARY = LibraryLocatorV2.from_string("lib:MITx:enabled")
ENABLED_V1_LIBRARY = LibraryLocator(org="MITx", library="enabled")
DISABLED_COURSE = CourseKey.from_string("course-v1:MITx+Disabled+1T2026")
MISSING_COURSE = "course-v1:MITx+Missing+1T2026"


class TestExportToGitCommand(TestCase):
    """Tests for which keys the command queues, skips, and reports."""

    def setUp(self):
        for key, enabled in (
            (ENABLED_COURSE, True),
            (ENABLED_LIBRARY, True),
            (ENABLED_V1_LIBRARY, True),
            (DISABLED_COURSE, False),
        ):
            ContentGitRepository.objects.create(
                content_key=key,
                git_url=f"git@github.com:org/{key}.git",
                is_export_enabled=enabled,
            )
        patcher = mock.patch(
            "ol_openedx_git_auto_export.utils.export_content_to_git", return_value=True
        )
        self.mock_export = patcher.start()
        self.addCleanup(patcher.stop)

    def run_command(self, *args, expect_error=False):
        out = StringIO()
        with pytest.raises(CommandError) if expect_error else nullcontext():
            call_command("export_to_git", *args, stdout=out)
        return out.getvalue()

    def exported_keys(self):
        return {call.args[0] for call in self.mock_export.call_args_list}

    def test_content_keys_queues_only_enabled_rows(self):
        out = self.run_command(
            "--content-keys",
            str(ENABLED_COURSE),
            str(ENABLED_COURSE),
            str(ENABLED_LIBRARY),
            str(DISABLED_COURSE),
            MISSING_COURSE,
            "not-a-key",
            expect_error=True,
        )

        assert self.mock_export.call_count == 2  # noqa: PLR2004
        assert self.exported_keys() == {ENABLED_COURSE, ENABLED_LIBRARY}
        assert "Queued 2 export(s)" in out
        assert f"{DISABLED_COURSE}: export disabled" in out
        assert f"{MISSING_COURSE}: no ContentGitRepository" in out
        assert "not-a-key: invalid key" in out

    def test_all_queues_every_enabled_row(self):
        self.run_command("--all")

        assert self.exported_keys() == {
            ENABLED_COURSE,
            ENABLED_LIBRARY,
            ENABLED_V1_LIBRARY,
        }

    def test_all_does_not_fail_on_skips(self):
        self.mock_export.return_value = False

        out = self.run_command("--all")

        assert "Queued 0 export(s)" in out
        assert "auto-export disabled in settings" in out

    def test_dry_run_passes_through_and_still_reports_skips(self):
        self.mock_export.side_effect = [True, False]

        out = self.run_command(
            "--dry-run",
            "--content-keys",
            str(ENABLED_COURSE),
            str(ENABLED_LIBRARY),
            str(DISABLED_COURSE),
            expect_error=True,
        )

        assert all(
            call.kwargs == {"dry_run": True} for call in self.mock_export.call_args_list
        )
        assert "Would queue 1 export(s)" in out
        assert f"{ENABLED_LIBRARY}: auto-export disabled in settings" in out
        assert f"{DISABLED_COURSE}: export disabled" in out

    def test_reports_settings_disabled_and_errors(self):
        self.mock_export.side_effect = [False, RuntimeError("broker down")]

        out = self.run_command(
            "--content-keys",
            str(ENABLED_COURSE),
            str(ENABLED_LIBRARY),
            expect_error=True,
        )

        assert "Queued 0 export(s)" in out
        assert f"{ENABLED_COURSE}: auto-export disabled in settings" in out
        assert f"{ENABLED_LIBRARY}: broker down" in out

    def test_skips_content_that_no_longer_exists(self):
        self.mock_export.side_effect = ContentNotFoundError

        out = self.run_command("--content-keys", str(ENABLED_COURSE), expect_error=True)

        assert f"{ENABLED_COURSE}: content not found" in out

    def test_requires_exactly_one_target(self):
        with pytest.raises(CommandError):
            self.run_command()
        with pytest.raises(CommandError):
            self.run_command("--all", "--content-keys", str(ENABLED_COURSE))


class TestExportToGitAdminAction(TestCase):
    """Tests for the ContentGitRepository admin action."""

    def test_reports_each_outcome(self):
        failing_course = CourseKey.from_string("course-v1:MITx+Failing+1T2026")
        for key, enabled in (
            (ENABLED_COURSE, True),
            (ENABLED_LIBRARY, True),
            (DISABLED_COURSE, False),
            (failing_course, True),
        ):
            ContentGitRepository.objects.create(
                content_key=key,
                git_url="git@github.com:org/x.git",
                is_export_enabled=enabled,
            )
        outcomes = {ENABLED_COURSE: True, ENABLED_LIBRARY: False}

        def fake_export(key, dry_run):  # noqa: ARG001
            if key not in outcomes:
                msg = "broker down"
                raise RuntimeError(msg)
            return outcomes[key]

        model_admin = ContentGitRepositoryAdmin(ContentGitRepository, AdminSite())
        with (
            mock.patch(
                "ol_openedx_git_auto_export.utils.export_content_to_git",
                side_effect=fake_export,
            ) as mock_export,
            mock.patch.object(model_admin, "message_user") as mock_message,
        ):
            model_admin.export_to_git(mock.Mock(), ContentGitRepository.objects.all())

        assert DISABLED_COURSE not in {c.args[0] for c in mock_export.call_args_list}
        assert [call.args[1] for call in mock_message.call_args_list] == [
            "Queued 1 git export(s).",
            "Skipped 2: 1 export disabled, 1 auto-export disabled in settings.",
            f"Failed to queue 1: {failing_course}: broker down",
        ]

    def test_action_requires_change_permission(self):
        model_admin = ContentGitRepositoryAdmin(ContentGitRepository, AdminSite())

        def actions_for(*codenames):
            user = User.objects.create_user(f"user-{'-'.join(codenames)}")
            user.is_staff = True
            user.save()
            user.user_permissions.set(Permission.objects.filter(codename__in=codenames))
            request = RequestFactory().get("/")
            request.user = User.objects.get(pk=user.pk)  # drop the perm cache
            return model_admin.get_actions(request)

        assert "export_to_git" not in actions_for("view_contentgitrepository")
        assert "export_to_git" in actions_for(
            "view_contentgitrepository", "change_contentgitrepository"
        )
