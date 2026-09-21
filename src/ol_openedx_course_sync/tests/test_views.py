"""
Tests for the ol-openedx-course-sync instructor dashboard endpoint.
"""

import json
from http import HTTPStatus
from unittest import mock

from common.djangoapps.student.tests.factories import UserFactory
from ddt import ddt, named_data, unpack
from django.test import RequestFactory
from ol_openedx_course_sync.constants import ACTION_RESET_ATTEMPTS, STATUS_SUBMITTED
from ol_openedx_course_sync.views import sync_problem_actions
from openedx.core.djangolib.testing.utils import skip_unless_lms
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

SUBMIT_PATH = "ol_openedx_course_sync.views.submit_problem_action_for_synced_courses"


@ddt
@skip_unless_lms
class SyncProblemActionsViewTests(ModuleStoreTestCase):
    """Tests for the sync_problem_actions endpoint.

    The view function is invoked directly via RequestFactory (rather than the
    Django test client) so the test does not depend on the full session/auth
    middleware stack.
    """

    def setUp(self):
        super().setUp()
        self.course = CourseFactory.create()
        self.course_id = str(self.course.id)
        self.problem_id = str(self.course.id.make_usage_key("problem", "test_problem"))
        self.staff_user = UserFactory.create(is_staff=True)
        self.factory = RequestFactory()

    def _post(self, user, course_id=None, **post_data):
        post_data.setdefault("action", ACTION_RESET_ATTEMPTS)
        post_data.setdefault("problem_id", self.problem_id)
        course_id = course_id or self.course_id
        request = self.factory.post(
            f"/courses/{course_id}/course_sync_actions/api/sync_problem_actions",
            data=post_data,
        )
        request.user = user
        return sync_problem_actions(request, course_id=course_id)

    def test_forbidden_for_non_staff(self):
        """A user without the platform staff flag gets a 403."""
        response = self._post(UserFactory.create())

        assert response.status_code == HTTPStatus.FORBIDDEN

    @named_data(
        ["unknown_action", {"action": "delete_everything"}],
        ["invalid_course_key", {"course_id": "not-a-course-key"}],
        ["invalid_problem_key", {"problem_id": "not-a-problem-key"}],
    )
    def test_rejects_bad_input(self, overrides):
        """Unknown actions and unparseable keys are rejected before submitting."""
        with mock.patch(SUBMIT_PATH) as mock_submit:
            response = self._post(self.staff_user, **overrides)

        assert response.status_code == HTTPStatus.BAD_REQUEST
        mock_submit.assert_not_called()

    def test_submits_action_and_returns_per_course_results(self):
        """A valid request returns the per-course result rows from the fan-out."""
        results = [
            {
                "course_id": self.course_id,
                "action": ACTION_RESET_ATTEMPTS,
                "status": STATUS_SUBMITTED,
                "task_id": "task-1",
            }
        ]
        with mock.patch(SUBMIT_PATH, return_value=results):
            response = self._post(self.staff_user)

        assert response.status_code == HTTPStatus.OK
        assert json.loads(response.content) == {"results": results}

    @named_data(
        ["omitted", {}, True],
        ["explicit_true", {"only_if_higher": "true"}, True],
        ["explicit_false", {"only_if_higher": "false"}, False],
    )
    @unpack
    def test_only_if_higher_defaults_on(self, overrides, expected):
        """Absent or true keeps the safe default; only an explicit false disables it."""
        with mock.patch(SUBMIT_PATH, return_value=[]) as mock_submit:
            self._post(self.staff_user, **overrides)

        assert mock_submit.call_args.kwargs["only_if_higher"] is expected
