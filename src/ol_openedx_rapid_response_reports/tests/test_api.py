"""Tests for the rapid response reports API"""

import json
from datetime import UTC, datetime
from http import HTTPStatus
from unittest.mock import patch

from common.djangoapps.student.roles import CourseStaffRole
from common.djangoapps.student.tests.factories import UserFactory
from django.test import RequestFactory
from ol_openedx_rapid_response_reports.api import list_rapid_response_runs
from openedx.core.djangolib.testing.utils import skip_unless_lms
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


@skip_unless_lms
class ListRapidResponseRunsViewTests(ModuleStoreTestCase):
    """Tests for the list_rapid_response_runs endpoint.

    The view function is invoked directly via RequestFactory so the test does not
    depend on the full session/auth middleware stack. ``get_run_data_for_course``
    (from the ``rapid_response_xblock`` dependency) is patched on the ``api`` module
    so the tests control the run data without touching its storage.
    """

    def setUp(self):
        super().setUp()
        self.course = CourseFactory.create()
        self.course_id = str(self.course.id)
        self.staff = UserFactory.create()
        CourseStaffRole(self.course.id).add_users(self.staff)
        self.factory = RequestFactory()

    def _get(self, user):
        request = self.factory.get(
            f"/courses/{self.course_id}/instructor/api/rapid_response_runs"
        )
        request.user = user
        return list_rapid_response_runs(request, course_id=self.course_id)

    def test_requires_course_permission(self):
        """A user without dashboard permission gets a 403."""
        assert self._get(UserFactory.create()).status_code == HTTPStatus.FORBIDDEN

    @patch(
        "ol_openedx_rapid_response_reports.api.get_run_data_for_course",
        return_value=[],
    )
    def test_returns_empty_list_when_no_runs(self, mock_runs):
        response = self._get(self.staff)
        assert response.status_code == HTTPStatus.OK
        assert json.loads(response.content) == []
        mock_runs.assert_called_once()

    @patch(
        "ol_openedx_rapid_response_reports.api.get_display_name_from_usage_key",
        return_value="My Rapid Problem",
    )
    @patch("ol_openedx_rapid_response_reports.api.get_run_data_for_course")
    def test_serializes_runs(self, mock_runs, mock_display_name):
        """Runs are serialized as a JSON array with the expected fields."""
        usage_key = "block-v1:org+course+run+type@problem+block@p1"
        mock_runs.return_value = [
            {
                "id": 7,
                "created": datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
                "problem_usage_key": usage_key,
            }
        ]

        response = self._get(self.staff)

        assert response.status_code == HTTPStatus.OK
        data = json.loads(response.content)
        assert isinstance(data, list)
        assert len(data) == 1
        run = data[0]
        assert run["id"] == "7"
        assert run["problem_usage_key"] == usage_key
        assert run["problem_display_name"] == "My Rapid Problem"
        assert run["created"].startswith("2026-01-02T03:04:05")
        mock_display_name.assert_called_once()
