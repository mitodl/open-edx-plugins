"""Just here to verify tests are running"""
from unittest import mock
import pytest

from ddt import data, ddt, unpack
from django.http.request import HttpRequest

from opaque_keys.edx.keys import UsageKey
from opaque_keys.edx.locator import CourseLocator
from tests.utils import (
    combine_dicts,
    make_scope_ids,
    RuntimeEnabledTestCase,
)
from rapid_response_xblock.models import (
    RapidResponseRun,
    RapidResponseSubmission,
)
from rapid_response_xblock.logger import SubmissionRecorder
from xmodule.modulestore.django import modulestore
from lms.djangoapps.courseware.block_render import load_single_xblock


# pylint: disable=no-member
@pytest.mark.usefixtures("example_event")
@ddt
class TestEvents(RuntimeEnabledTestCase):
    """Tests for event capturing"""

    def setUp(self):
        super().setUp()
        self.scope_ids = make_scope_ids(self.block)
        # For the test_data course
        self.test_data_status = RapidResponseRun.objects.create(
            problem_usage_key=UsageKey.from_string(
                "block-v1:SGAU+SGA101+2017_SGA+type@problem+block@2582bbb68672426297e525b49a383eb8"
            ),
            course_key=CourseLocator.from_string(
                'course-v1:SGAU+SGA101+2017_SGA'
            ),
            open=True,
        )

        # For the block id in example_event.json
        usage_key = UsageKey.from_string(
            "block-v1:ReplaceStatic+ReplaceStatic+2018_T1+type@problem+block@2582bbb68672426297e525b49a383eb8"
        )
        self.example_status = RapidResponseRun.objects.create(
            problem_usage_key=usage_key,
            course_key=usage_key.course_key,
            open=True,
        )

    def get_problem(self):
        """
        Get the problem from the test course
        """
        course = self.course
        store = modulestore()
        problem = [
            item for item in store.get_items(course.course_id)
            if item.__class__.__name__ == 'ProblemBlockWithMixins'
        ][0]
        problem.bind_for_student(self.instructor)

        # Workaround handle_ajax binding strangeness
        request = HttpRequest()
        request.META['SERVER_NAME'] = 'mit.edu'
        request.META['SERVER_PORT'] = 1234
        return load_single_xblock(
            request=request,
            course_id=str(self.course_id),
            user_id=self.instructor.id,
            usage_key_string=str(problem.location),
            will_recheck_access=True
        )

    def test_publish(self):
        """
        Make sure the Logger is installed correctly
        """
        event_type = 'event_name'
        event_object = {'a': 'data'}

        # If this package is installed TRACKING_BACKENDS should
        # be configured to point to SubmissionRecorder. Since self.runtime is
        # an LmsModuleSystem, self.runtime.publish will send the event
        # to all registered loggers.
        block = self.course
        with mock.patch.object(
            SubmissionRecorder, 'send', autospec=True,
        ) as send_patch:
            self.runtime.publish(block, event_type, event_object)
        # If call_count is 0, make sure you installed
        # this package first to allow detection of the logger
        assert send_patch.call_count == 1
        event = send_patch.call_args[0][1]

        assert event['name'] == 'event_name'
        assert event['context']['event_source'] == 'server'
        assert event['data'] == event_object
        assert event['context']['course_id'] == "course-v1:{org}+{course}+{run}".format(
            org=block.location.org,
            course=block.location.course,
            run=block.location.run,
        )

    @data(*[
        ['choice_0', 'an incorrect answer'],
        ['choice_1', 'the correct answer'],
        ['choice_2', 'a different incorrect answer'],
    ])
    @unpack
    def test_problem(self, clicked_answer_id, expected_answer_text):
        """
        A problem should trigger an event which is captured
        """
        problem = self.get_problem()

        problem.handle_ajax('problem_check', {
            "input_2582bbb68672426297e525b49a383eb8_2_1": clicked_answer_id
        })
        assert RapidResponseSubmission.objects.count() == 1
        obj = RapidResponseSubmission.objects.first()
        assert obj.user_id == self.instructor.id
        assert obj.run.course_key == self.course.course_id
        assert obj.run.problem_usage_key.map_into_course(
            self.course.course_id
        ) == problem.location
        assert obj.answer_text == expected_answer_text
        assert obj.answer_id == clicked_answer_id

    def test_multiple_submissions(self):
        """
        Only the last submission should get captured
        """
        problem = self.get_problem()
        for answer in ('choice_0', 'choice_1', 'choice_2'):
            problem.handle_ajax('problem_check', {
                "input_2582bbb68672426297e525b49a383eb8_2_1": answer
            })

        assert RapidResponseSubmission.objects.count() == 1
        obj = RapidResponseSubmission.objects.first()
        assert obj.user_id == self.instructor.id
        assert obj.run.course_key == self.course.course_id
        assert obj.run.problem_usage_key.map_into_course(
            self.course.course_id
        ) == problem.location
        # Answer is the first one clicked
        assert obj.answer_text == 'a different incorrect answer'
        assert obj.answer_id == 'choice_2'  # the last one picked

    def assert_successful_event_parsing(self, example_event_data):
        """
        Assert what happens when the event is parsed
        """
        assert RapidResponseSubmission.objects.count() == 1
        obj = RapidResponseSubmission.objects.first()
        assert obj.user_id == example_event_data['context']['user_id']
        assert obj.run.problem_usage_key == UsageKey.from_string(
            example_event_data['data']['problem_id']
        )
        assert obj.run.course_key == CourseLocator.from_string(
            example_event_data['context']['course_id']
        )
        # Answer is the first one clicked
        assert obj.answer_text == 'an incorrect answer'
        assert obj.answer_id == 'choice_0'
        assert obj.event == example_event_data

    def assert_unsuccessful_event_parsing(self):
        """
        Assert that no event was recorded
        """
        assert RapidResponseSubmission.objects.count() == 0

    def test_example_event(self):
        """
        Assert that the example event is a valid one
        """
        SubmissionRecorder().send(self.example_event)
        self.assert_successful_event_parsing(self.example_event)

    def test_missing_user(self):
        """
        If the user is missing no exception should be raised
        and no event should be recorded
        """
        del self.example_event['context']['user_id']
        SubmissionRecorder().send(self.example_event)
        self.assert_unsuccessful_event_parsing()

    def test_missing_problem_id(self):
        """
        If the problem id is missing no event should be recorded
        """
        del self.example_event['data']['problem_id']
        SubmissionRecorder().send(self.example_event)
        self.assert_unsuccessful_event_parsing()

    def test_extra_submission(self):
        """
        If there is more than one submission in the event,
        no event should be recorded
        """
        submission = list(self.example_event['data']['submission'].values())[0]
        self.example_event['data']['submission']['new_key'] = submission
        SubmissionRecorder().send(self.example_event)
        self.assert_unsuccessful_event_parsing()

    @data(None, {})
    def test_no_submission(self, submission_value):
        """
        If there is no submission or an empty submission in the event,
        no event should be recorded
        """
        key = list(self.example_event['data']['submission'].keys())[0]
        self.example_event['data']['submission'][key] = submission_value
        SubmissionRecorder().send(self.example_event)
        self.assert_unsuccessful_event_parsing()

    def test_missing_event_data(self):
        """
        If the event data is missing no event should be recorded
        """
        self.example_event['data'] = []
        SubmissionRecorder().send(self.example_event)
        self.assert_unsuccessful_event_parsing()

    def test_missing_answer_id(self):
        """
        If the answer id key is missing no event should be recorded
        """
        self.example_event['data']['answers'] = {}
        SubmissionRecorder().send(self.example_event)
        self.assert_unsuccessful_event_parsing()

    def test_submission_less_than_one(self):
        """
        If the submission data is less than 1,
        no event should be recorded
        """
        self.example_event['data']['submission'] = {}
        SubmissionRecorder().send(self.example_event)
        self.assert_unsuccessful_event_parsing()

    def test_submission_more_than_two(self):
        """
        If the submission data is more than 2,
        no event should be recorded
        """
        submission = list(self.example_event['data']['submission'].values())[0]
        self.example_event['data']['submission']['new_key_1'] = submission
        self.example_event['data']['submission']['new_key_2'] = submission
        SubmissionRecorder().send(self.example_event)
        self.assert_unsuccessful_event_parsing()

    @pytest.mark.usefixtures("example_event")
    def test_open(self):
        """
        Events should be recorded only when the problem is open
        """
        event = self.example_event
        event_before = combine_dicts(event, {'test_data': 'before'})
        event_during = combine_dicts(event, {'test_data': 'during'})
        event_after = combine_dicts(event, {'test_data': 'after'})

        self.example_status.open = False
        self.example_status.save()

        recorder = SubmissionRecorder()
        recorder.send(event_before)
        self.example_status.open = True
        self.example_status.save()
        recorder.send(event_during)
        self.example_status.open = False
        self.example_status.save()
        recorder.send(event_after)

        assert RapidResponseSubmission.objects.count() == 1
        submission = RapidResponseSubmission.objects.first()
        assert submission.event['test_data'] == event_during['test_data']

    @pytest.mark.usefixtures("example_event")
    def test_last_open(self):
        """
        Only the last run should be considered
        """
        RapidResponseRun.objects.create(
            problem_usage_key=self.example_status.problem_usage_key,
            course_key=self.example_status.course_key,
            open=False,
        )

        recorder = SubmissionRecorder()
        recorder.send(self.example_event)
        # The last run has open=False so no submissions should be recorded
        assert RapidResponseSubmission.objects.count() == 0
