"""Open edX Filters pipeline steps for the course sync plugin."""

import logging
from urllib.parse import urlparse

from common.djangoapps.student.roles import GlobalStaff
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext as _
from openedx_filters import PipelineStep

from ol_openedx_course_sync.constants import COURSE_SYNC_TAB_ID
from ol_openedx_course_sync.utils import get_syncable_course_mappings

log = logging.getLogger(__name__)


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

    def _is_sync_source(self, course_key):
        """
        Whether the course is an active sync source.

        A missing service worker username makes ``get_syncable_course_mappings``
        raise, and this runs while building every instructor dashboard. Whether
        that surfaces as a 500 depends on the ``fail_silently`` of whatever
        ``OPEN_EDX_FILTERS_CONFIG`` the deployment ends up with, so an
        unconfigured plugin drops the tab here rather than relying on that.
        """
        try:
            return bool(get_syncable_course_mappings(course_key))
        except ImproperlyConfigured:
            log.warning(
                "Course sync is not fully configured; omitting the %s tab for %s.",
                COURSE_SYNC_TAB_ID,
                course_key,
            )
            return False

    def run_filter(self, tabs, user, course_key):
        """Run the pipeline step."""
        # GlobalStaff().has_user() is `user.is_staff`, but tolerates user being None.
        if GlobalStaff().has_user(user) and self._is_sync_source(course_key):
            already_present = any(
                tab.get("tab_id") == COURSE_SYNC_TAB_ID for tab in tabs
            )
            if not already_present:
                # Land after every existing tab; built-in sort_order values aren't fixed.
                next_sort_order = (
                    max((tab.get("sort_order", 0) for tab in tabs), default=0) + 10
                )
                tabs.append(
                    {
                        "tab_id": COURSE_SYNC_TAB_ID,
                        "title": _("Course Sync Actions"),
                        "url": build_instructor_dashboard_tab_url(
                            course_key, COURSE_SYNC_TAB_ID
                        ),
                        "sort_order": next_sort_order,
                    }
                )

        # Return all filter args so later pipeline steps still receive them.
        return {"tabs": tabs, "user": user, "course_key": course_key}
