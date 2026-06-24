"""Tests for the Canvas integration MFE endpoints."""

import json
from http import HTTPStatus
from unittest.mock import patch

from common.djangoapps.student.roles import CourseInstructorRole
from common.djangoapps.student.tests.factories import UserFactory
from django.test import RequestFactory, override_settings
from lms.djangoapps.instructor_task.models import InstructorTask
from ol_openedx_canvas_integration.views import list_canvas_tasks
from openedx.core.djangolib.testing.utils import skip_unless_lms
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


@skip_unless_lms
@override_settings(BULK_EMAIL_DEFAULT_RETRY_DELAY=10, BULK_EMAIL_MAX_RETRIES=5)
class ListCanvasTasksViewTests(ModuleStoreTestCase):
    """Tests for the list_canvas_tasks endpoint.

    The view function is invoked directly via RequestFactory (rather than the
    Django test client) so the test does not depend on the full session/auth
    middleware stack.
    """

    def setUp(self):
        super().setUp()
        self.course = CourseFactory.create()
        self.course_id = str(self.course.id)
        self.instructor = UserFactory.create()
        CourseInstructorRole(self.course.id).add_users(self.instructor)
        self.factory = RequestFactory()

    def _get(self, user):
        request = self.factory.get(
            f"/courses/{self.course_id}/canvas/api/list_canvas_tasks"
        )
        request.user = user
        return list_canvas_tasks(request, course_id=self.course_id)

    def _create_canvas_task(self, task_type, results):
        task = InstructorTask.create(
            course_id=self.course.id,
            task_type=task_type,
            task_key="",
            task_input={},
            requester=self.instructor,
        )
        task.task_state = "SUCCESS"
        task.task_output = json.dumps({"results": results, "duration_ms": 1000})
        task.save()
        return task

    def test_requires_course_permission(self):
        """A user without instructor permission gets a 403."""
        assert self._get(UserFactory.create()).status_code == HTTPStatus.FORBIDDEN

    def test_returns_empty_list_when_no_tasks(self):
        response = self._get(self.instructor)
        assert response.status_code == HTTPStatus.OK
        assert json.loads(response.content) == {"tasks": []}

    def test_lists_canvas_tasks(self):
        """Canvas tasks are returned, serialized with the expected fields."""
        self._create_canvas_task(
            "push_edx_grades_to_canvas", {"grades": 3, "assignments": 2}
        )

        response = self._get(self.instructor)

        assert response.status_code == HTTPStatus.OK
        tasks = json.loads(response.content)["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["task_type"] == "push_edx_grades_to_canvas"
        assert tasks[0]["requester"] == self.instructor.username

    def test_canvas_message_uses_plugin_formatter(self):
        """The task message is produced by the plugin's own formatter, so the
        endpoint does not depend on the edx-platform cherry-pick."""
        self._create_canvas_task(
            "sync_canvas_enrollments", {"grades": 0, "assignments": 0}
        )

        with patch(
            "ol_openedx_canvas_integration.views.get_task_output_formatted_message",
            return_value="CANVAS SENTINEL MESSAGE",
        ):
            response = self._get(self.instructor)

        assert response.status_code == HTTPStatus.OK
        tasks = json.loads(response.content)["tasks"]
        assert tasks[0]["task_message"] == "CANVAS SENTINEL MESSAGE"
