"""Open edX Filters pipeline steps for the Canvas integration plugin."""

from urllib.parse import urlparse

from django.conf import settings
from django.utils.translation import gettext as _
from openedx_filters import PipelineStep
from xmodule.modulestore.django import modulestore

from ol_openedx_canvas_integration.constants import CANVAS_TAB_ID
from ol_openedx_canvas_integration.utils import get_canvas_course_id


def build_instructor_dashboard_tab_url(course_key, tab_id):
    """
    Build the MFE-internal URL for an instructor dashboard tab.

    Derives the path from ``settings.INSTRUCTOR_MICROFRONTEND_URL`` (using only its
    path component, the same way the LMS builds the built-in tab URLs) so our tab
    links stay consistent with the standard instructor dashboard tabs instead of
    hardcoding the ``/apps`` mount point.
    """
    base_url = getattr(settings, "INSTRUCTOR_MICROFRONTEND_URL", None) or ""
    base_path = urlparse(base_url).path.rstrip("/")
    return "/".join([base_path, str(course_key).strip("/"), tab_id])


class AddCanvasInstructorTab(PipelineStep):
    """
    Add a "Canvas" tab to the instructor dashboard MFE when the course is linked
    to a Canvas course.

    Mirrors the legacy gating in ``context_api.plugin_context``: the tab is only
    surfaced when ``canvas_id`` is set in the course's "Other course settings".
    Hooks into the ``InstructorDashboardTabsRequested`` filter
    (``org.openedx.learning.instructor.dashboard.tabs.requested.v1``).

    The tab ``url`` is an MFE-internal (root-relative) path so the instructor
    dashboard renders the page registered in the routes slot
    (``createInstructorDashboardCustomApp`` in the shared MFE module) without a
    full page reload.
    """

    def run_filter(self, tabs, user, course_key):
        course = modulestore().get_course(course_key)
        if course and get_canvas_course_id(course):
            already_present = any(tab.get("tab_id") == CANVAS_TAB_ID for tab in tabs)
            if not already_present:
                # Append after every tab currently in the list so the Canvas tab
                # always lands at the end, regardless of the built-in tabs' own
                # sort_order values (which are not fixed and may change).
                next_sort_order = (
                    max((tab.get("sort_order", 0) for tab in tabs), default=0) + 10
                )
                tabs.append(
                    {
                        "tab_id": CANVAS_TAB_ID,
                        "title": _("Canvas"),
                        "url": build_instructor_dashboard_tab_url(
                            course_key, CANVAS_TAB_ID
                        ),
                        "sort_order": next_sort_order,
                    }
                )

        # Return the full filter payload (tabs, user, course_key) so the filter
        # and any subsequent pipeline step receive every argument.
        return {"tabs": tabs, "user": user, "course_key": course_key}
