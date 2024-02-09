"""
Provide tests for sysadmin dashboard feature in sysadmin.py
"""

import glob
import os
import shutil
from datetime import datetime
from uuid import uuid4

from common.djangoapps.student.roles import CourseStaffRole, GlobalStaff
from common.djangoapps.student.tests.factories import UserFactory
from common.djangoapps.util.date_utils import DEFAULT_DATE_TIME_FORMAT, get_time_display
from django.conf import settings
from django.test.client import Client
from django.test.utils import override_settings
from django.urls import reverse
from edx_sysadmin.git_import import GitImportNoDirError
from edx_sysadmin.models import CourseGitLog
from opaque_keys.edx.locator import CourseLocator
from openedx.core.djangolib.markup import Text
from pytz import UTC
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.django_utils import (
    TEST_DATA_SPLIT_MODULESTORE,
    SharedModuleStoreTestCase,
)


class SysadminBaseTestCase(SharedModuleStoreTestCase):  # pragma: allowlist secret
    """
    Base class with common methods used in XML and Mongo tests
    """

    TEST_REPO = "https://github.com/edx/edx4edx_lite.git"
    TEST_BRANCH = "testing_do_not_delete"
    TEST_BRANCH_COURSE = CourseLocator.from_string(
        "course-v1:MITx+edx4edx_branch+edx4edx"
    )
    MODULESTORE = TEST_DATA_SPLIT_MODULESTORE

    def setUp(self):
        """Add primary user in test case Setup"""
        super().setUp()
        self.user = UserFactory.create(
            username="test_user",
            email="test_user+sysadmin@edx.org",
            password="foo",  # pragma: allowlist secret  # noqa: S106
        )
        self.client = Client()

    def _setstaff_login(self):
        """Make the test user staff and logs them in"""
        GlobalStaff().add_users(self.user)
        self.client.login(
            username=self.user.username,
            password="foo",  # pragma: allowlist secret  # noqa: S106
        )

    def _add_edx4edx(self, branch=None):
        """Add the edx4edx sample course"""
        post_dict = {
            "repo_location": self.TEST_REPO,
            "action": "add_course",
        }
        if branch:
            post_dict["repo_branch"] = branch
        return self.client.post(reverse("sysadmin:gitimport"), post_dict)

    def _rm_edx4edx(self):
        """Delete the sample course from the XML store"""
        def_ms = modulestore()
        course_path = (
            f"{os.path.abspath(settings.DATA_DIR)}/edx4edx_lite"  # noqa: PTH100
        )
        try:
            # using XML store
            course = def_ms.courses.get(course_path, None)
        except AttributeError:
            # Using mongo store
            course = def_ms.get_course(CourseLocator("MITx", "edx4edx", "edx4edx"))

        # Delete git loaded course
        if course:
            response = self.client.post(
                reverse("sysadmin:courses"),
                {
                    "course_id": str(course.id),
                    "action": "del_course",
                },
            )
            self.addCleanup(self._rm_glob, f"{course_path}_deleted_*")

            return response
        else:
            return None

    def _rm_glob(self, path):
        """
        Create a shell expansion of passed in parameter and iteratively
        remove them.  Must only expand to directories.
        """
        for path in glob.glob(  # noqa: PTH207, B020
            path
        ):  # lint-amnesty, pylint: disable=redefined-argument-from-local
            shutil.rmtree(path)

    def _mkdir(self, path):
        """
        Create directory and add the cleanup for it.
        """
        os.mkdir(path)  # noqa: PTH102
        self.addCleanup(shutil.rmtree, path)


@override_settings(
    GIT_REPO_DIR=settings.TEST_ROOT / f"course_repos_{uuid4().hex}",
)
class TestSysAdminMongoCourseImport(SysadminBaseTestCase):
    """
    Check that importing into the mongo module store works
    """

    @classmethod
    def tearDownClass(cls):
        """Delete mongo log entries after test."""
        super().tearDownClass()
        CourseGitLog.objects.all().delete()

    def _setstaff_login(self):
        """
        Make the test user staff and logs them in
        """

        self.user.is_staff = True
        self.user.save()

        self.client.login(
            username=self.user.username,
            password="foo",  # pragma: allowlist secret  # noqa: S106
        )

    def test_missing_repo_dir(self):
        """
        Ensure that we handle a missing repo dir
        """

        self._setstaff_login()

        if os.path.isdir(settings.GIT_REPO_DIR):  # noqa: PTH112
            shutil.rmtree(settings.GIT_REPO_DIR)

        # Create git loaded course
        response = self._add_edx4edx()
        self.assertContains(
            response, Text(str(GitImportNoDirError(settings.GIT_REPO_DIR)))
        )

    def test_mongo_course_add_delete(self):
        """
        This is the same as TestSysadmin.test_xml_course_add_delete,
        but it uses a mongo store
        """

        self._setstaff_login()
        self._mkdir(settings.GIT_REPO_DIR)

        def_ms = modulestore()
        assert def_ms.get_modulestore_type(None) != "xml"

        self._add_edx4edx()
        course = def_ms.get_course(CourseLocator("MITx", "edx4edx", "edx4edx"))
        assert course is not None

        self._rm_edx4edx()
        course = def_ms.get_course(CourseLocator("MITx", "edx4edx", "edx4edx"))
        assert course is None

    def test_gitlogs(self):
        """
        Create a log entry and make sure it exists
        """

        self._setstaff_login()
        self._mkdir(settings.GIT_REPO_DIR)

        self._add_edx4edx()
        response = self.client.get(reverse("sysadmin:gitlogs"))

        # Check that our earlier import has a log with a link to details
        self.assertContains(response, "/gitlogs/course-v1:MITx+edx4edx+edx4edx")

        response = self.client.get(
            reverse(
                "sysadmin:gitlogs_detail",
                kwargs={"course_id": "course-v1:MITx+edx4edx+edx4edx"},
            )
        )

        self.assertContains(response, "======&gt; IMPORTING course")

        self._rm_edx4edx()

    def test_gitlog_date(self):
        """
        Make sure the date is timezone-aware and being converted/formatted
        properly.
        """

        tz_names = [
            "America/New_York",  # UTC - 5
            "Asia/Pyongyang",  # UTC + 9
            "Europe/London",  # UTC
            "Canada/Yukon",  # UTC - 8
            "Europe/Moscow",  # UTC + 4
        ]
        tz_format = DEFAULT_DATE_TIME_FORMAT

        self._setstaff_login()
        self._mkdir(settings.GIT_REPO_DIR)

        self._add_edx4edx()
        date = CourseGitLog.objects.all().first().created.replace(tzinfo=UTC)

        for timezone in tz_names:
            with override_settings(
                TIME_ZONE=timezone
            ):  # lint-amnesty, pylint: disable=superfluous-parens
                date_text = get_time_display(date, tz_format, settings.TIME_ZONE)
                response = self.client.get(reverse("sysadmin:gitlogs"))
                self.assertContains(response, date_text)

        self._rm_edx4edx()

    def test_gitlog_bad_course(self):
        """
        Make sure we gracefully handle courses that don't exist.
        """
        self._setstaff_login()
        response = self.client.get(
            reverse("sysadmin:gitlogs_detail", kwargs={"course_id": "Not/Real/Testing"})
        )
        self.assertContains(
            response,
            "No git import logs have been recorded for this course.",
        )

    def test_gitlog_no_logs(self):
        """
        Make sure the template behaves well when rendered despite there not being any logs.
        (This is for courses imported using methods other than the git_add_course command)
        """  # noqa: E501

        self._setstaff_login()
        self._mkdir(settings.GIT_REPO_DIR)

        self._add_edx4edx()

        # Simulate a lack of git import logs
        import_logs = CourseGitLog.objects.all()
        import_logs.delete()

        response = self.client.get(
            reverse(
                "sysadmin:gitlogs_detail",
                kwargs={"course_id": "course-v1:MITx+edx4edx+edx4edx"},
            )
        )

        self.assertContains(
            response, "No git import logs have been recorded for this course."
        )

        self._rm_edx4edx()

    def test_gitlog_pagination_out_of_range_invalid(self):
        """
        Make sure the pagination behaves properly when the requested page is out
        of range.
        """

        self._setstaff_login()

        for _ in range(15):
            CourseGitLog(
                course_id=CourseLocator.from_string("test/test/test"),
                course_import_log="import_log",
                git_log="git_log",
                repo_dir="repo_dir",
                created=datetime.now(),  # noqa: DTZ005
            ).save()

        for page, expected in [(-1, 1), (1, 1), (2, 2), (30, 2), ("abc", 1)]:
            response = self.client.get(
                "{}?page={}".format(reverse("sysadmin:gitlogs"), page)
            )
            self.assertContains(response, f"Page {expected} of 2")

        CourseGitLog.objects.all().delete()

    def test_gitlog_courseteam_access(self):
        """
        Ensure course team users are allowed to access only their own course.
        """

        self._mkdir(settings.GIT_REPO_DIR)

        self._setstaff_login()
        self._add_edx4edx()
        self.user.is_staff = False
        self.user.save()
        self.user.courseaccessrole_set.all().delete()
        logged_in = self.client.login(
            username=self.user.username,
            password="foo",  # noqa: S106  # pragma: allowlist secret
        )
        response = self.client.get(reverse("sysadmin:gitlogs"))
        # Make sure our non privileged user doesn't have access to all logs
        assert response.status_code == 302  # noqa: PLR2004
        assert response.url == "/404"
        # Or specific logs
        response = self.client.get(
            reverse(
                "sysadmin:gitlogs_detail",
                kwargs={"course_id": "course-v1:MITx+edx4edx+edx4edx"},
            )
        )
        assert response.status_code == 302  # noqa: PLR2004
        assert response.url == "/404"

        # Add user as staff in course team
        self.user.is_staff = True
        self.user.save()
        def_ms = modulestore()
        course = def_ms.get_course(CourseLocator("MITx", "edx4edx", "edx4edx"))
        CourseStaffRole(course.id).add_users(self.user)

        assert CourseStaffRole(course.id).has_user(self.user)
        logged_in = self.client.login(
            username=self.user.username,
            password="foo",  # noqa: S106  # pragma: allowlist secret
        )
        assert logged_in

        response = self.client.get(
            reverse(
                "sysadmin:gitlogs_detail",
                kwargs={"course_id": "course-v1:MITx+edx4edx+edx4edx"},
            )
        )
        self.assertContains(response, "======&gt; IMPORTING course")

        self._rm_edx4edx()
