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
from xblock.fields import Scope, String

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
        default=_("OL Chat XBlock"),
        scope=Scope.settings,
        help=_(
            "This name appears in the horizontal navigation at the top of the page."
        ),
    )
    course_id = String(
        default="",
        scope=Scope.settings,
        help=_("Course ID of the relevant course in Canvas"),
    )
    editable_fields = ("display_name", "course_id")

    def student_view(self, context=None):  # noqa: ARG002
        """Render the student view of the block."""
        fragment = Fragment("")
        fragment.add_content(
            render_template(
                "static/html/student_view.html",
                {
                    "block_id": self.usage_key.block_id,
                },
            )
        )
        fragment.add_javascript(get_resource_bytes("static/js/lms.js"))
        fragment.add_css(get_resource_bytes("static/css/ai_chat_xblock.css"))
        fragment.initialize_js(
            "OLChatBlock", json_args={"block_id": self.usage_key.block_id}
        )
        return fragment

    def author_view(self, context=None):  # noqa: ARG002
        """
        Render the author view of the block.
        """
        fragment = Fragment("")
        fragment.add_content(
            render_template(
                "static/html/studio_view.html",
                {
                    "block_id": self.usage_key.block_id,
                },
            )
        )
        fragment.add_javascript(get_resource_bytes("static/js/studio.js"))
        fragment.add_css(get_resource_bytes("static/css/ai_chat_xblock.css"))
        fragment.initialize_js(
            "OLChatBlock", json_args={"block_id": self.usage_key.block_id}
        )
        return fragment

    @XBlock.handler
    def ol_chat(self, request, suffix=""):  # noqa: ARG002
        """Start the chat session via external MIT LEARN AI API."""
        try:
            request_data = request.json
        except Exception:  # noqa: BLE001
            log.warning("Invalid JSON in chat request.")
            return Response(
                "Invalid request body. Expected JSON.",
                status=api_status.HTTP_400_BAD_REQUEST,
            )

        api_url = settings.MIT_LEARN_AI_XBLOCK_CHAT_API_URL
        api_token = settings.MIT_LEARN_AI_XBLOCK_CHAT_API_TOKEN

        if not api_url or not api_token:
            log.error("Missing AI API configuration (URL or token).")
            return Response(
                "Missing API configurations. Please check your settings.",
                status=api_status.HTTP_400_BAD_REQUEST,
            )

        if not self.course_id:
            log.error("Course ID is not set for the XBlock.")
            return Response(
                "Course ID is required.",
                status=api_status.HTTP_400_BAD_REQUEST,
            )

        message = request_data.get("message", "").strip()
        if not message:
            return Response(
                "Message field is required.",
                status=api_status.HTTP_400_BAD_REQUEST,
            )

        payload = {
            "collection_name": "content_files",
            "message": message,
            "course_id": self.course_id,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_token}",
        }

        try:
            # Use the cookies from the request to maintain session state
            # This is important for the MIT Learn AI service to track user sessions
            block_id = self.usage_key.block_id
            req_syllabusbot_ai_threads_anon = request.cookies.get(
                "SyllabusBot_ai_threads_anon", None
            )
            req_block_id = request.cookies.get("block_id", None)

            if req_block_id != block_id:
                req_syllabusbot_ai_threads_anon = None

            req_cookies = {
                "SyllabusBot_ai_threads_anon": req_syllabusbot_ai_threads_anon
            }
            response = requests.post(
                api_url, json=payload, headers=headers, timeout=60, cookies=req_cookies
            )

            # Check if the response was successful.
            response.raise_for_status()
            resp_syllabusbot_ai_threads_anon = response.cookies.get(
                "SyllabusBot_ai_threads_anon"
            )
            xblock_response = Response(response.content)
            xblock_response.set_cookie(
                "SyllabusBot_ai_threads_anon",
                resp_syllabusbot_ai_threads_anon,
                httponly=True,
            )
            xblock_response.set_cookie("block_id", block_id, httponly=True)
            return xblock_response  # noqa: TRY300

        except requests.exceptions.RequestException as e:
            log.exception("Failed to contact MIT Learn AI service.")
            return Response(
                {
                    "error": "Failed to connect to MIT Learn AI service.",
                    "details": str(e),
                },
                status=api_status.HTTP_502_BAD_GATEWAY,
            )
