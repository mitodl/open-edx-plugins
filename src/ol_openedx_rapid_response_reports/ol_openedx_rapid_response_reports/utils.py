from django.core.cache import cache
from rapid_response_xblock.utils import get_run_data_for_course
from xmodule.modulestore.django import modulestore

from ol_openedx_rapid_response_reports.constants import (
    RAPID_RESPONSE_ASIDE_TYPE,
    RAPID_RESPONSE_ENABLED_CACHE_TIMEOUT,
)


def get_display_name_from_usage_key(key, course):
    """
    Returns problem display name from given block UsageKey.
    Args:
        key (UsageKey) : Usage key of block
    Returns:
        String : Returns the display name of block if exists else 'Deleted'.
    """  # noqa: D401
    block = course.get_child(key)
    if block:
        return block.display_name
    else:
        return "Deleted"


def is_rapid_response_enabled_for_course(course_key):
    """
    Return True if rapid response is enabled for at least one problem in the course.

    Rapid response has no course-level setting; it is switched on per problem
    through the rapid response aside's ``enabled`` field. Scanning every problem is
    too slow to do on each instructor dashboard load, so the result is cached
    against the course's published version, which changes on every publish.
    """
    store = modulestore()
    course = store.get_course(course_key)
    if course is None:
        return False

    cache_key = (
        f"ol_rapid_response_reports.enabled.{course_key}.{course.course_version}"
    )
    enabled = cache.get(cache_key)
    if enabled is None:
        enabled = any(
            problem.runtime.get_aside_of_type(
                problem, RAPID_RESPONSE_ASIDE_TYPE
            ).enabled
            for problem in store.get_items(
                course_key, qualifiers={"category": "problem"}
            )
        )
        cache.set(cache_key, enabled, RAPID_RESPONSE_ENABLED_CACHE_TIMEOUT)
    return enabled


def should_show_rapid_response_tab(course_key):
    """
    Return True if the instructor dashboard should show the Rapid Responses tab.

    The tab is shown while rapid response is enabled for a problem in the course,
    and also once the course has any run, so reports for past runs stay reachable
    after rapid response is switched off again.
    """
    return get_run_data_for_course(
        course_key=course_key
    ).exists() or is_rapid_response_enabled_for_course(course_key)
