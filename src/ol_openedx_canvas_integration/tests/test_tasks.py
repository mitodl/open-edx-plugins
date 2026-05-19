"""Tests for Canvas integration tasks"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from lms.djangoapps.grades.models import PersistentSubsectionGrade
from ol_openedx_canvas_integration.tasks import _sync_user_grade_with_canvas
from opaque_keys.edx.keys import CourseKey, UsageKey
from openedx.core.djangolib.testing.utils import skip_unless_lms
from pytz import UTC

USER_MODEL = get_user_model()


@override_settings(BULK_EMAIL_DEFAULT_RETRY_DELAY=10, BULK_EMAIL_MAX_RETRIES=5)
@patch("ol_openedx_canvas_integration.tasks.submit_task", MagicMock(return_value=None))
@patch(
    "ol_openedx_canvas_integration.tasks.get_course_by_id",
    MagicMock(return_value=MagicMock()),
)
@skip_unless_lms
class TestSyncUserGradeWithCanvas(TestCase):
    """Tests for _sync_user_grade_with_canvas task"""

    def setUp(self):
        """Setup test data"""
        self.grade_id = 123
        self.course_id = CourseKey.from_string("course-v1:org+course+run")
        self.usage_key = UsageKey.from_string(
            "block-v1:org+course+run+type@sequential+block@subsection"
        )
        self.canvas_course_id = "canvas-123"
        self.email = "student@example.com"
        self.canvas_user_id = 456
        self.canvas_assignment_id = 789
        self.user = USER_MODEL.objects.create_user(
            username="student",
            email="student@example.com",
            password="password",  # noqa: S106 # pragma: allowlist secret
        )
        self.grade_instance = PersistentSubsectionGrade.update_or_create_grade(
            user_id=self.user.id,
            id=self.grade_id,
            course_id=self.course_id,
            usage_key=self.usage_key,
            earned_all=6.0,
            possible_all=12.0,
            earned_graded=6.0,
            possible_graded=8.0,
            visible_blocks=[],
            first_attempted=datetime.now(tz=UTC),
        )
        # Mock Course
        self.course = MagicMock()

    @patch("ol_openedx_canvas_integration.tasks.CanvasClient")
    @patch("ol_openedx_canvas_integration.tasks.get_subsection_user_grades")
    @patch("ol_openedx_canvas_integration.tasks.TASK_LOG")
    @patch(
        "ol_openedx_canvas_integration.tasks.get_canvas_course_id",
        MagicMock(return_value="canvas-123"),
    )
    def test_sync_success(
        self,
        mock_task_log,
        mock_get_grades,
        mock_client_class,
    ):
        """Test successful grade sync to Canvas"""
        mock_client = mock_client_class.return_value
        mock_client.get_canvas_assignments.return_value = {
            str(self.usage_key): {
                "id": self.canvas_assignment_id,
                "due_at": "",
            }
        }
        mock_client.get_student_id_by_email.return_value = self.canvas_user_id
        mock_client.update_assignment_grades.return_value = MagicMock(
            status_code=requests.codes.ok
        )

        grade_obj = MagicMock()
        grade_obj.percent_graded = 0.85
        mock_get_grades.return_value = {self.usage_key: {self.user: grade_obj}}

        _sync_user_grade_with_canvas(self.grade_id)

        mock_client.update_assignment_grades.assert_called_once()

        mock_task_log.error.assert_not_called()

    @patch("ol_openedx_canvas_integration.tasks.CanvasClient")
    @patch(
        "ol_openedx_canvas_integration.tasks.get_canvas_course_id",
        MagicMock(return_value=None),
    )
    def test_no_canvas_id(
        self,
        mock_client_class,
    ):

        _sync_user_grade_with_canvas(self.grade_id)

        mock_client_class.assert_not_called()

    @patch("ol_openedx_canvas_integration.tasks.CanvasClient")
    @patch(
        "ol_openedx_canvas_integration.tasks.get_canvas_course_id",
        MagicMock(return_value="canvas-123"),
    )
    def test_assignment_not_synced(
        self,
        mock_client_class,
    ):
        mock_client = mock_client_class.return_value
        mock_client.get_canvas_assignments.return_value = {
            "dummy-key": {
                "id": self.canvas_assignment_id,
                "due_at": "",
            }
        }

        _sync_user_grade_with_canvas(self.grade_id)

        mock_client.update_assignment_grades.assert_not_called()

    @patch("ol_openedx_canvas_integration.tasks.CanvasClient")
    @patch(
        "ol_openedx_canvas_integration.tasks.get_canvas_course_id",
        MagicMock(return_value="canvas-123"),
    )
    def test_assignment_past_due_date(
        self,
        mock_client_class,
    ):
        mock_client = mock_client_class.return_value
        mock_client.get_canvas_assignments.return_value = {
            "dummy-key": {
                "id": self.canvas_assignment_id,
                "due_at": str(datetime.now(tz=UTC) - timedelta(days=1)),
            }
        }

        _sync_user_grade_with_canvas(self.grade_id)

        mock_client.update_assignment_grades.assert_not_called()

    @patch("ol_openedx_canvas_integration.tasks.CanvasClient")
    @patch(
        "ol_openedx_canvas_integration.tasks.get_canvas_course_id",
        MagicMock(return_value="canvas-123"),
    )
    def test_no_canvas_user_id(
        self,
        mock_client_class,
    ):
        mock_client = mock_client_class.return_value
        mock_client.get_canvas_assignments.return_value = {
            str(self.usage_key): {
                "id": self.canvas_assignment_id,
                "due_at": "",
            }
        }
        mock_client.get_student_id_by_email.return_value = None

        _sync_user_grade_with_canvas(self.grade_id)

        mock_client.update_assignment_grades.assert_not_called()

    @patch("ol_openedx_canvas_integration.tasks.CanvasClient")
    @patch("ol_openedx_canvas_integration.tasks.get_subsection_user_grades")
    @patch(
        "ol_openedx_canvas_integration.tasks.get_canvas_course_id",
        MagicMock(return_value="canvas-123"),
    )
    def test_sync_key_error(
        self,
        mock_get_grades,
        mock_client_class,
    ):
        """Test successful grade sync to Canvas"""
        mock_client = mock_client_class.return_value
        mock_client.get_canvas_assignments.return_value = {
            str(self.usage_key): {
                "id": self.canvas_assignment_id,
                "due_at": "",
            }
        }
        mock_client.get_student_id_by_email.return_value = self.canvas_user_id
        mock_client.update_assignment_grades.return_value = MagicMock(
            status_code=requests.codes.ok
        )

        grade_obj = MagicMock()
        grade_obj.percent_graded = 0.85
        mock_get_grades.return_value = {"dummy-key": {self.user: grade_obj}}

        _sync_user_grade_with_canvas(self.grade_id)

        mock_client.update_assignment_grades.assert_not_called()

    @patch("ol_openedx_canvas_integration.tasks.CanvasClient")
    @patch("ol_openedx_canvas_integration.tasks.get_subsection_user_grades")
    @patch("ol_openedx_canvas_integration.tasks.TASK_LOG")
    @patch(
        "ol_openedx_canvas_integration.tasks.get_canvas_course_id",
        MagicMock(return_value="canvas-123"),
    )
    def test_sync_fail_code(
        self,
        mock_task_log,
        mock_get_grades,
        mock_client_class,
    ):
        mock_client = mock_client_class.return_value
        mock_client.get_canvas_assignments.return_value = {
            str(self.usage_key): {
                "id": self.canvas_assignment_id,
                "due_at": "",
            }
        }
        mock_client.get_student_id_by_email.return_value = self.canvas_user_id
        mock_client.update_assignment_grades.return_value = MagicMock(status_code=502)

        grade_obj = MagicMock()
        grade_obj.percent_graded = 0.85
        mock_get_grades.return_value = {self.usage_key: {self.user: grade_obj}}

        _sync_user_grade_with_canvas(self.grade_id)

        mock_client.update_assignment_grades.assert_called_once()

        mock_task_log.error.assert_called_once()
