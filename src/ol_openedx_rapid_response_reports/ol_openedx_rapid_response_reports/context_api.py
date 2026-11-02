"""
ol_openedx_rapid_response_reports Django application plugin context initialization.
"""

from django.utils.translation import gettext as _
from rapid_response_xblock.utils import get_run_data_for_course
from web_fragments.fragment import Fragment

from ol_openedx_rapid_response_reports.utils import is_rapid_response_enabled_for_course


def plugin_context(context):
    """Provide data for the rapid responses dashboard section"""
    course_key = context["course"].id
    # Only show the section for courses that use rapid response on some problem
    if not is_rapid_response_enabled_for_course(course_key):
        return context

    sections = context.get("sections", [])

    rapid_response_context = {
        "section_key": "rapid_response",
        "section_display_name": _("Rapid Responses"),
        "problem_runs": get_run_data_for_course(course_key=course_key),
        "course_key": course_key,
        "download_url": "get_rapid_response_report",
        "fragment": Fragment(),
        "template_path_prefix": "/",
    }
    sections.append(rapid_response_context)
    context["sections"] = sections

    return context
