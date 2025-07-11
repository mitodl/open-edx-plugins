import logging

import pkg_resources
import requests
from django.conf import settings
from django.template import Context, Template
from django.utils.translation import gettext_lazy as _
from rest_framework import status as api_status
from web_fragments.fragment import Fragment
from webob.response import Response
from xblock.core import XBlock
from xblock.fields import Integer, Scope, String

try:
    from xblock.utils.studio_editable import StudioEditableXBlockMixin
except (
    ModuleNotFoundError
):  # For backward compatibility with releases older than Quince.
    from xblockutils.studio_editable import StudioEditableXBlockMixin

log = logging.getLogger(__name__)


def get_resource_bytes(path):
    """
    Helper method to get the unicode contents of a resource in this repo.

    Args:
        path (str): The path of the resource

    Returns:
        unicode: The unicode contents of the resource at the given path
    """  # noqa: D401
    resource_contents = pkg_resources.resource_string(__name__, path)
    return resource_contents.decode("utf-8")


def render_template(template_path, context=None):
    """
    Evaluate a template by resource path, applying the provided context.
    """
    context = context or {}
    template_str = get_resource_bytes(template_path)
    template = Template(template_str)
    return template.render(Context(context))


class OLChatXBlock(XBlock, StudioEditableXBlockMixin):
    """
    XBlock that enables OL AI Chat functionality in Open edX
    """

    display_name = String(
        display_name=_("Display Name"),
        default=_("Ol Chat XBlock"),
        scope=Scope.settings,
        help=_(
            "This name appears in the horizontal navigation at the top of the page."
        ),
    )
    course_id = Integer(
        default=0,
        scope=Scope.settings,
        help=_("Course ID of the relevant course in Canvas"),
    )
    editable_fields = ("display_name", "course_id")

    def student_view(self, context=None):  # noqa: ARG002
        """
        Render the student view of the block.
        """

        html = "<div>THIS IS THE STUDENT VIEW OF THE CHAT XBLOCK</div>"
        return Fragment(html)

    @XBlock.handler
    def ol_chat(self, request, suffix=""):  # noqa: ARG002
        """Start the chat session via external AI API."""

        api_url = settings.MIT_LEARN_XBLOCK_AI_API_URL
        api_token = settings.MIT_LEARN_XBLOCK_AI_API_TOKEN

        if not api_url or not api_token:
            log.error("Missing AI API configuration (URL or token).")
            return Response(
                {"error": "Missing API configurations. Please check your settings."},
                status=api_status.HTTP_400_BAD_REQUEST,
                content_type="application/json",
            )

        try:
            request_data = request.json
        except Exception:  # noqa: BLE001
            log.warning("Invalid JSON in chat request.")
            return Response(
                {"error": "Invalid request body. Expected JSON."},
                status=api_status.HTTP_400_BAD_REQUEST,
                content_type="application/json",
            )

        message = request_data.get("message", "").strip()
        if not message:
            return Response(
                {"error": "Message field is required."},
                status=api_status.HTTP_400_BAD_REQUEST,
                content_type="application/json",
            )

        payload = {
            "collection_name": "content_files",
            "message": message,
            "course_id": str(self.course_id),  # ensure it's JSON-safe
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_token}",
        }

        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            return Response(
                response.text,
                status=response.status_code,
                content_type=response.headers.get("Content-Type", "application/json"),
            )
        except requests.exceptions.RequestException as e:
            log.exception("Failed to contact MIT Learn AI service.")
            return Response(
                {
                    "error": "Failed to connect to MIT Learn AI service.",
                    "details": str(e),
                },
                status=api_status.HTTP_502_BAD_GATEWAY,
                content_type="application/json",
            )
