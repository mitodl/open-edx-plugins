"""Open edX Filters pipeline steps for the rapid response reports plugin."""

from urllib.parse import urlparse

from django.conf import settings
from django.utils.translation import gettext as _
from openedx_filters import PipelineStep

from ol_openedx_rapid_response_reports.constants import RAPID_RESPONSE_TAB_ID
from ol_openedx_rapid_response_reports.utils import should_show_rapid_response_tab


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


class AddRapidResponseInstructorTab(PipelineStep):
    """
    Add a "Rapid Responses" tab to the instructor dashboard MFE.

    Hooks into the ``InstructorDashboardTabsRequested`` filter
    (``org.openedx.learning.instructor.dashboard.tabs.requested.v1``). The tab is
    only appended for courses with rapid response enabled on a problem or with a
    past run (see ``utils.should_show_rapid_response_tab``), mirroring the legacy
    ``context_api.plugin_context``.

    The tab ``url`` is an MFE-internal (root-relative) path so the instructor
    dashboard renders the page registered in the routes slot
    (``createInstructorDashboardCustomApp`` in the shared MFE module).
    """

    def run_filter(self, tabs, user, course_key):
        already_present = any(
            tab.get("tab_id") == RAPID_RESPONSE_TAB_ID for tab in tabs
        )
        if not already_present and should_show_rapid_response_tab(course_key):
            # Append after every tab currently in the list so the tab always lands
            # at the end, regardless of the built-in tabs' own sort_order values.
            next_sort_order = (
                max((tab.get("sort_order", 0) for tab in tabs), default=0) + 10
            )
            tabs.append(
                {
                    "tab_id": RAPID_RESPONSE_TAB_ID,
                    "title": _("Rapid Responses"),
                    "url": build_instructor_dashboard_tab_url(
                        course_key, RAPID_RESPONSE_TAB_ID
                    ),
                    "sort_order": next_sort_order,
                }
            )

        # Return the full filter payload (tabs, user, course_key) so the filter
        # and any subsequent pipeline step receive every argument.
        return {"tabs": tabs, "user": user, "course_key": course_key}
