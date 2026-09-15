"""Open edX Filters pipeline steps for the course sync plugin."""

from urllib.parse import urlparse

from common.djangoapps.student.roles import GlobalStaff
from django.conf import settings
from django.utils.translation import gettext as _
from openedx_filters import PipelineStep

from ol_openedx_course_sync.constants import COURSE_SYNC_TAB_ID
from ol_openedx_course_sync.utils import get_syncable_course_mappings


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


class AddCourseSyncInstructorTab(PipelineStep):
    """
    Add a "Course Sync" tab to the instructor dashboard MFE for staff users on
    courses that are an active sync source.

    Target (rerun) courses do not get the tab: problem actions are always keyed off
    a source course's problem and fanned out to its targets from there.

    Hooks into the ``InstructorDashboardTabsRequested`` filter
    (``org.openedx.learning.instructor.dashboard.tabs.requested.v1``).
    """

    def run_filter(self, tabs, user, course_key):
        """Append the Course Sync tab to the instructor dashboard tab list."""
        # GlobalStaff().has_user() is `user.is_staff`, but tolerates user being None.
        if GlobalStaff().has_user(user) and get_syncable_course_mappings(course_key):
            already_present = any(
                tab.get("tab_id") == COURSE_SYNC_TAB_ID for tab in tabs
            )
            if not already_present:
                # Append after every tab currently in the list so our tab always
                # lands at the end, regardless of the built-in tabs' own
                # sort_order values (which are not fixed and may change).
                next_sort_order = (
                    max((tab.get("sort_order", 0) for tab in tabs), default=0) + 10
                )
                tabs.append(
                    {
                        "tab_id": COURSE_SYNC_TAB_ID,
                        "title": _("Course Sync"),
                        "url": build_instructor_dashboard_tab_url(
                            course_key, COURSE_SYNC_TAB_ID
                        ),
                        "sort_order": next_sort_order,
                    }
                )

        # Return the full filter payload (tabs, user, course_key) so the filter
        # and any subsequent pipeline step receive every argument.
        return {"tabs": tabs, "user": user, "course_key": course_key}
