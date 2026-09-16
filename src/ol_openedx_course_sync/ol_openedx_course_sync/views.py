"""Views for the ol-openedx-course-sync plugin"""

import logging

from common.djangoapps.util.json_request import JsonResponse
from common.djangoapps.util.views import require_global_staff
from django.db import transaction
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey, UsageKey

from ol_openedx_course_sync.constants import VALID_ACTIONS
from ol_openedx_course_sync.utils import submit_problem_action_for_synced_courses

log = logging.getLogger(__name__)


@transaction.non_atomic_requests
@require_POST
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@require_global_staff
def sync_problem_actions(request, course_id):
    """
    Reset attempts or rescore a problem across a course and all its synced reruns.

    The course is taken from the URL, not the request body. Learners in every
    active target course of ``course_id`` are affected, as well as the course
    itself.
    """
    action = request.POST.get("action")
    if action not in VALID_ACTIONS:
        return JsonResponse({"error": f"Invalid action: {action}"}, status=400)

    try:
        source_course_key = CourseKey.from_string(course_id)
    except InvalidKeyError:
        return JsonResponse({"error": f"Invalid course key: {course_id}"}, status=400)

    problem_id = request.POST.get("problem_id", "")
    try:
        problem_usage_key = UsageKey.from_string(problem_id)
    except InvalidKeyError:
        return JsonResponse(
            {"error": f"Invalid problem usage key: {problem_id}"}, status=400
        )

    # Defaults to True: rescoring without it can lower an existing score.
    only_if_higher = request.POST.get("only_if_higher", "true").lower() == "true"

    log.info(
        "Submitting %s for problem %s in course %s (requested by %s)",
        action,
        problem_id,
        course_id,
        request.user.username,
    )
    results = submit_problem_action_for_synced_courses(
        request,
        source_course_key,
        problem_usage_key,
        action,
        only_if_higher=only_if_higher,
    )
    return JsonResponse({"results": results})
