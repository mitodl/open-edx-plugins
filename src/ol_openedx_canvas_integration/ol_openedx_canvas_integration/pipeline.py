"""Open edX Filters pipeline steps for the Canvas integration plugin."""

import logging

from django.utils.translation import gettext as _
from openedx_filters import PipelineStep
from xmodule.modulestore.django import modulestore

from ol_openedx_canvas_integration.utils import get_canvas_course_id

log = logging.getLogger(__name__)

CANVAS_TAB_ID = "canvas_integration"
CANVAS_TAB_SORT_ORDER = 110


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

    def run_filter(self, tabs, course_key, **kwargs):  # noqa: ARG002
        try:
            course = modulestore().get_course(course_key)
            if course and get_canvas_course_id(course):
                already_present = any(
                    tab.get("tab_id") == CANVAS_TAB_ID for tab in tabs
                )
                if not already_present:
                    tabs.append(
                        {
                            "tab_id": CANVAS_TAB_ID,
                            "title": _("Canvas"),
                            "url": (
                                f"/instructor-dashboard/{course_key}/{CANVAS_TAB_ID}"
                            ),
                            "sort_order": CANVAS_TAB_SORT_ORDER,
                        }
                    )
        except Exception:
            # Never let a Canvas lookup failure break instructor dashboard tabs.
            log.exception(
                "Failed to evaluate Canvas instructor tab for course %s", course_key
            )

        return {"tabs": tabs}
