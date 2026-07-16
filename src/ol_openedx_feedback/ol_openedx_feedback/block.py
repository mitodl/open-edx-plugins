"""XBlockAside that renders the per-block feedback trigger."""

import logging

import pkg_resources
from django.conf import settings
from django.template import Context, Template
from django.utils.translation import gettext
from web_fragments.fragment import Fragment
from xblock.core import XBlockAside
from xmodule.x_module import STUDENT_VIEW

from ol_openedx_feedback.compat import get_feedback_enabled_flag
from ol_openedx_feedback.utils import is_aside_applicable_to_block

log = logging.getLogger(__name__)


def _resource(path):
    """Return the decoded contents of a packaged resource."""
    return pkg_resources.resource_string(__name__, path).decode("utf-8")


def _render(path, context):
    """Render a packaged Django template with the given context."""
    return Template(_resource(path)).render(Context(context))


class FeedbackAside(XBlockAside):
    """Adds a small 'Send feedback' trigger to applicable blocks in the LMS."""

    @XBlockAside.aside_for(STUDENT_VIEW)
    def student_view_aside(self, block, context=None):  # noqa: ARG002
        """Render the feedback trigger for authenticated learners only."""
        fragment = Fragment("")

        # Never render in Studio author/preview or for anonymous/preview users.
        if getattr(self.runtime, "is_author_mode", False) or not getattr(
            self.runtime, "user_id", None
        ):
            return fragment

        block_usage_key = block.usage_key
        block_id = block_usage_key.block_id
        block_type = getattr(block, "category", None)

        fragment.add_content(
            _render(
                "static/html/student_view.html",
                {
                    "block_id": block_id,
                    "label": gettext("Send feedback"),
                },
            )
        )
        fragment.add_css(_resource("static/css/feedback.css"))
        fragment.add_javascript(_resource("static/js/feedback.js"))
        fragment.initialize_js(
            "FeedbackAsideInit",
            json_args={
                "block_id": block_id,
                "learning_mfe_base_url": getattr(
                    settings, "LEARNING_MICROFRONTEND_URL", ""
                ),
                "drawer_payload": {
                    "courseId": str(block_usage_key.course_key),
                    "blockUsageKey": str(block_usage_key),
                    "blockType": block_type,
                    "blockDisplayName": block.display_name or "",
                },
            },
        )
        return fragment

    @classmethod
    def should_apply_to_block(cls, block):
        """Apply to leaf blocks when the course waffle flag is enabled."""
        return get_feedback_enabled_flag().is_enabled(
            block.scope_ids.usage_id.context_key
        ) and is_aside_applicable_to_block(block)
