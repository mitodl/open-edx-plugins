"""Tests for the rapid response reports MFE endpoint."""

import json
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from common.djangoapps.student.roles import CourseStaffRole
from common.djangoapps.student.tests.factories import UserFactory
from django.test import RequestFactory
from ol_openedx_rapid_response_reports.api import list_rapid_response_runs
from openedx.core.djangolib.testing.utils import skip_unless_lms
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


@contextmanager
def fake_rapid_response_runs(runs):
    """Stub ``rapid_response_xblock.utils`` for the duration of the block.

    The view lazily imports ``get_run_data_for_course`` from
    ``rapid_response_xblock.utils``. That package is a separate plugin and is not
    a declared dependency, so it may not be importable in the test environment
    (CI installs plugins alphabetically and cumulatively, running these tests
    before ``rapid_response_xblock`` is installed). Injecting a stub module makes
    the lazy import resolve deterministically and lets us control the run data.
    """
    utils_stub = MagicMock()
    utils_stub.get_run_data_for_course.return_value = runs
    parent_stub = MagicMock()
    parent_stub.utils = utils_stub
    with patch.dict(
        sys.modules,
        {
            "rapid_response_xblock": parent_stub,
            "rapid_response_xblock.utils": utils_stub,
        },
    ):
        yield utils_stub


@skip_unless_lms
class ListRapidResponseRunsViewTests(ModuleStoreTestCase):
    """Tests for the list_rapid_response_runs endpoint.

    The view function is invoked directly via RequestFactory so the test does not
    depend on the full session/auth middleware stack.
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

    def test_returns_empty_list_when_no_runs(self):
        with fake_rapid_response_runs([]):
            response = self._get(self.staff)
        assert response.status_code == HTTPStatus.OK
        assert json.loads(response.content) == []

    @patch(
        "ol_openedx_rapid_response_reports.utils.get_display_name_from_usage_key",
        return_value="My Rapid Problem",
    )
    def test_serializes_runs(self, mock_display_name):  # noqa: ARG002
        """Runs are serialized as a JSON array with the expected fields."""
        usage_key = "block-v1:org+course+run+type@problem+block@p1"
        runs = [
            {
                "id": 7,
                "created": datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
                "problem_usage_key": usage_key,
            }
        ]

        with fake_rapid_response_runs(runs):
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
