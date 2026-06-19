"""Open edX Filters pipeline steps for the rapid response reports plugin."""

import logging

from django.utils.translation import gettext as _
from openedx_filters import PipelineStep

log = logging.getLogger(__name__)

RAPID_RESPONSE_TAB_ID = "rapid_response"
RAPID_RESPONSE_TAB_SORT_ORDER = 120


class AddRapidResponseInstructorTab(PipelineStep):
    """
    Add a "Rapid Responses" tab to the instructor dashboard MFE.

    Hooks into the ``InstructorDashboardTabsRequested`` filter
    (``org.openedx.learning.instructor.dashboard.tabs.requested.v1``). The tab is
    appended unconditionally, mirroring the legacy ``context_api.plugin_context``
    which always surfaces the section (no per-course gating). Because this step is
    only registered when this plugin is installed, the tab appears solely on
    deployments that actually have rapid response reports available.

    The tab ``url`` is an MFE-internal (root-relative) path so the instructor
    dashboard renders the page registered in the routes slot
    (``createInstructorDashboardCustomApp`` in the shared MFE module).
    """

    def run_filter(self, tabs, course_key, **kwargs):  # noqa: ARG002
        already_present = any(
            tab.get("tab_id") == RAPID_RESPONSE_TAB_ID for tab in tabs
        )
        if not already_present:
            tabs.append(
                {
                    "tab_id": RAPID_RESPONSE_TAB_ID,
                    "title": _("Rapid Responses"),
                    "url": (
                        f"/instructor-dashboard/{course_key}/{RAPID_RESPONSE_TAB_ID}"
                    ),
                    "sort_order": RAPID_RESPONSE_TAB_SORT_ORDER,
                }
            )
        return {"tabs": tabs}
