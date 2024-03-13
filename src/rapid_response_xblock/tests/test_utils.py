"""Tests for the util methods"""
import pytest
from opaque_keys.edx.keys import UsageKey

from tests.utils import RuntimeEnabledTestCase
from rapid_response_xblock.models import RapidResponseRun, RapidResponseSubmission
from rapid_response_xblock.utils import get_run_data_for_course, get_run_submission_data
from common.djangoapps.student.tests.factories import UserFactory


class TestUtils(RuntimeEnabledTestCase):
    """Utils method tests"""

    def setUp(self):
        super().setUp()
        self.problem_run = RapidResponseRun.objects.create(
            problem_usage_key=UsageKey.from_string("i4x://SGAU/SGA101/problem/2582bbb68672426297e525b49a383eb8"),
            course_key=self.course_id,
            open=True,
        )

    @pytest.mark.filterwarnings("ignore::DeprecationWarning")
    def test_get_run_data_for_course(self):
        """Verify that method returns list fo dicts with required fields."""
        expected = [
            {
                'id': self.problem_run.id,
                'created': self.problem_run.created,
                'problem_usage_key': self.problem_run.problem_usage_key
            }
        ]

        problem_runs = get_run_data_for_course(self.course_id)
        assert list(problem_runs) == expected

    def test_get_run_submission_data(self):
        user = UserFactory()
        answer = "false"
        event_data = {
            "event": {
                "submission": {
                    "123456": {
                        "correct": answer,
                    }
                }
            }
        }

        submission = RapidResponseSubmission.objects.create(run=self.problem_run, user=user, event=event_data)
        expected = [[
            submission.created, submission.answer_text, submission.user.username, submission.user.email, answer
        ]]
        submissions_data = get_run_submission_data(self.problem_run.id)

        assert submissions_data == expected
