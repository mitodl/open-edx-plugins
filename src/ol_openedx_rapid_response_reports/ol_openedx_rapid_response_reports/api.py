"""API views for the rapid response reports plugin."""

from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET
from lms.djangoapps.courseware.courses import get_course_by_id
from lms.djangoapps.instructor.permissions import VIEW_DASHBOARD
from lms.djangoapps.instructor.views.api import require_course_permission
from lms.djangoapps.instructor_analytics import csvs
from opaque_keys.edx.keys import CourseKey
from rapid_response_xblock.utils import (
    get_run_data_for_course,
    get_run_submission_data,
)

from ol_openedx_rapid_response_reports.utils import get_display_name_from_usage_key


@require_GET
@ensure_csrf_cookie
@require_course_permission(VIEW_DASHBOARD)
def list_rapid_response_runs(
    request,  # noqa: ARG001
    course_id,
):
    """Return JSON list of rapid response runs for the given course."""
    course_key = CourseKey.from_string(course_id)
    runs = get_run_data_for_course(course_key=course_key)
    course = get_course_by_id(course_key, depth=None)

    return JsonResponse(
        [
            {
                "id": str(run["id"]),
                "problem_usage_key": str(run["problem_usage_key"]),
                "problem_display_name": get_display_name_from_usage_key(
                    run["problem_usage_key"], course
                ),
                "created": run["created"].isoformat(),
            }
            for run in runs
        ],
        safe=False,
    )


@ensure_csrf_cookie
@require_course_permission(VIEW_DASHBOARD)
def get_rapid_response_report(
    request,  # noqa: ARG001
    course_id,  # noqa: ARG001
    run_id,
):  # pylint: disable=unused-argument
    """
    Return csv file corresponding to given run_id
    """
    header = ["Date", "Submitted Answer", "Username", "User Email", "Correct"]
    return csvs.create_csv_response(
        filename="rapid_response_submissions.csv",
        header=header,
        datarows=get_run_submission_data(run_id),
    )
