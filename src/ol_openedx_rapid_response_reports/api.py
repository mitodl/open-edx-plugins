from django.views.decorators.csrf import ensure_csrf_cookie
from lms.djangoapps.instructor.permissions import VIEW_DASHBOARD
from lms.djangoapps.instructor.views.api import require_course_permission
from lms.djangoapps.instructor_analytics import csvs


@ensure_csrf_cookie
@require_course_permission(VIEW_DASHBOARD)
def get_rapid_response_report(
    request, course_id, run_id
):  # pylint: disable=unused-argument
    """
    Return csv file corresponding to given run_id
    """
    header = ["Date", "Submitted Answer", "Username", "User Email", "Correct"]
    from rapid_response_xblock.utils import (
        get_run_submission_data,  # pylint: disable=import-error
    )

    return csvs.create_csv_response(
        filename="rapid_response_submissions.csv",
        header=header,
        datarows=get_run_submission_data(run_id),
    )
