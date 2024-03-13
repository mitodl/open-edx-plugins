"""
Capture events
"""
import logging
from collections import namedtuple

from django.db import transaction
from opaque_keys.edx.keys import UsageKey
from opaque_keys.edx.locator import CourseLocator
from rapid_response_xblock.models import (
    RapidResponseRun,
    RapidResponseSubmission,
)
from rapid_response_xblock.block import MULTIPLE_CHOICE_TYPE
from common.djangoapps.track.backends import BaseBackend


log = logging.getLogger(__name__)
SubmissionEvent = namedtuple(
    'SubmissionEvent',
    ['raw_data', 'user_id', 'problem_usage_key', 'course_key', 'answer_text', 'answer_id']
)


class SubmissionRecorder(BaseBackend):
    """
    Record events emitted by blocks.
    See TRACKING_BACKENDS for the configuration for this logger.
    For more information about events see:

    http://edx.readthedocs.io/projects/devdata/en/stable/
    internal_data_formats/tracking_logs.html
    """
    @staticmethod
    def parse_submission_event(event):
        """
        Attempts to parse raw event data as an answer submission for the problem types
        that rapid-response can be applied to. If the event is not an answer submission,
        or the given problem type is not applicable for rapid-response, None is returned.

        Args:
            event (dict): Raw event data

        Returns:
             SubmissionEvent: The parsed submission event data (or None)
        """
        # Ignore if this event was not the submission of an answer
        if event.get('name') != 'problem_check':
            return None
        # Ignore if there were multiple or no submissions represented in this single event
        event_data = event.get('data')
        if not event_data or not isinstance(event_data, dict):
            return None

        event_submissions = event_data.get('submission')
        if len(event_submissions) != 1:
            return None

        submission_key, submission = list(event_submissions.items())[0]
        # Ignore if the problem being answered has a blank submission or is not multiple choice
        if not submission or submission.get('response_type') != MULTIPLE_CHOICE_TYPE:
            return None

        try:
            return SubmissionEvent(
                raw_data=event,
                user_id=event['context']['user_id'],
                problem_usage_key=UsageKey.from_string(
                    event_data['problem_id']
                ),
                course_key=CourseLocator.from_string(
                    event['context']['course_id']
                ),
                answer_text=submission['answer'],
                answer_id=event_data['answers'][submission_key]
            )
        except:  # pylint: disable=bare-except
            log.exception("Unable to parse event data as a submission: %s", event)

    def send(self, event):
        sub = self.parse_submission_event(event)
        # If the event could not be parsed or was the wrong type, ignore it
        if sub is None:
            return

        open_run = RapidResponseRun.objects.filter(
            problem_usage_key=sub.problem_usage_key,
            course_key=sub.course_key
        ).order_by('-created').first()
        if not open_run or not open_run.open:
            # Problem is not open
            return

        # Delete any older responses for the user
        with transaction.atomic():
            RapidResponseSubmission.objects.filter(
                user_id=sub.user_id,
                run=open_run,
            ).delete()
            RapidResponseSubmission.objects.create(
                user_id=sub.user_id,
                run=open_run,
                event=sub.raw_data,
                answer_id=sub.answer_id,
                answer_text=sub.answer_text,
            )
