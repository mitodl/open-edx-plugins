"""Views for canvas integration"""
import logging

from common.djangoapps.student.models import CourseEnrollment, CourseEnrollmentAllowed
from common.djangoapps.util.json_request import JsonResponse
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.translation import ugettext as _
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from lms.djangoapps.courseware.courses import get_course_by_id
from lms.djangoapps.instructor import permissions
from lms.djangoapps.instructor.views.api import require_course_permission
from lms.djangoapps.instructor_task.api_helper import AlreadyRunningError
from opaque_keys.edx.locator import CourseLocator

from ol_openedx_canvas_integration import tasks
from ol_openedx_canvas_integration.client import CanvasClient

log = logging.getLogger(__name__)


def _get_edx_enrollment_data(email, course_key):
    """Helper function to look up some info regarding whether a user with a email address is enrolled in edx"""
    user = User.objects.filter(email=email).first()
    allowed = CourseEnrollmentAllowed.objects.filter(
        email=email, course_id=course_key
    ).first()

    return {
        "exists_in_edx": bool(user),
        "enrolled_in_edx": bool(
            user and CourseEnrollment.is_enrolled(user, course_key)
        ),
        "allowed_in_edx": bool(allowed),
    }


@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@require_course_permission(permissions.OVERRIDE_GRADES)
def list_canvas_enrollments(request, course_id):
    """
    Fetch enrollees for a course in canvas and list them
    """
    course_key = CourseLocator.from_string(course_id)
    course = get_course_by_id(course_key)
    if not course.canvas_course_id:
        raise Exception(f"No canvas_course_id set for course {course_id}")

    client = CanvasClient(canvas_course_id=course.canvas_course_id)
    # WARNING: this will block the web thread
    enrollment_dict = client.list_canvas_enrollments()

    results = [
        {"email": email, **_get_edx_enrollment_data(email, course_key)}
        for email in sorted(enrollment_dict.keys())
    ]
    return JsonResponse(results)


@transaction.non_atomic_requests
@require_POST
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@require_course_permission(permissions.OVERRIDE_GRADES)
def add_canvas_enrollments(request, course_id):
    """
    Fetches enrollees for a course in canvas and enrolls those emails in the course in edX
    """
    unenroll_current = request.POST.get("unenroll_current", "").lower() == "true"
    course_key = CourseLocator.from_string(course_id)
    course = get_course_by_id(course_key)
    if not course.canvas_course_id:
        raise Exception(f"No canvas_course_id set for course {course_id}")

    try:
        tasks.run_sync_canvas_enrollments(
            request=request,
            course_key=course_id,
            canvas_course_id=course.canvas_course_id,
            unenroll_current=unenroll_current,
        )
        log.info("Syncing canvas enrollments for course %s", course_id)
        success_status = _("Syncing canvas enrollments")
        return JsonResponse({"status": success_status})
    except AlreadyRunningError:
        already_running_status = _(
            "Syncing canvas enrollments. See Pending Tasks below to view the status."
        )
        return JsonResponse({"status": already_running_status})


@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@require_course_permission(permissions.OVERRIDE_GRADES)
def list_canvas_assignments(request, course_id):
    """List Canvas assignments"""
    course_key = CourseLocator.from_string(course_id)
    course = get_course_by_id(course_key)
    client = CanvasClient(canvas_course_id=course.canvas_course_id)
    if not course.canvas_course_id:
        raise Exception(f"No canvas_course_id set for course {course_id}")
    return JsonResponse(client.list_canvas_assignments())


@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@require_course_permission(permissions.OVERRIDE_GRADES)
def list_canvas_grades(request, course_id):
    """List grades"""
    assignment_id = int(request.GET.get("assignment_id"))
    course_key = CourseLocator.from_string(course_id)
    course = get_course_by_id(course_key)
    client = CanvasClient(canvas_course_id=course.canvas_course_id)
    if not course.canvas_course_id:
        raise Exception(f"No canvas_course_id set for course {course_id}")
    return JsonResponse(client.list_canvas_grades(assignment_id=assignment_id))


@transaction.non_atomic_requests
@require_POST
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@require_course_permission(permissions.OVERRIDE_GRADES)
def push_edx_grades(request, course_id):
    """Push user grades for all graded items in edX to Canvas"""
    course_key = CourseLocator.from_string(course_id)
    course = get_course_by_id(course_key)
    if not course.canvas_course_id:
        raise Exception(f"No canvas_course_id set for course {course_id}")
    try:
        tasks.run_push_edx_grades_to_canvas(
            request=request,
            course_id=course_id,
        )
        log.info("Pushing edX grades to canvas for course %s", course_id)
        success_status = _("Pushing edX grades to canvas")
        return JsonResponse({"status": success_status})
    except AlreadyRunningError:
        already_running_status = _(
            "Pushing edX grades to canvas. See Pending Tasks below to view the status."
        )
        return JsonResponse({"status": already_running_status})
