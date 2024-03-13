"""Utils methods for instructor dashboard"""

from rapid_response_xblock.models import RapidResponseRun, RapidResponseSubmission


def get_run_data_for_course(course_key):
    """Util method to return problem runs corresponding to given course key"""
    return RapidResponseRun.objects.filter(course_key=course_key).values('id', 'created', 'problem_usage_key')


def get_run_submission_data(run_id):
    """
    Return data required to generate csv file corresponding to given run_id
    """
    submissions = RapidResponseSubmission.objects.filter(run_id=run_id)
    return [
        [s.created, s.answer_text, s.user.username, s.user.email, get_answer_result(s.event)]
        for s in submissions
    ]


def get_answer_result(event):
    # TODO find better way if we can
    event_data = event.get('event', {}) or event.get('data', {})
    return list(
        event_data.get('submission').values()
    )[0]['correct']
