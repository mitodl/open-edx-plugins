import json
import logging
import re
from urllib.parse import urlencode

import pkg_resources
import requests
from crum import get_current_request
from django.conf import settings
from django.template import Context, Template
from eventtracking import tracker
from rest_framework import status as api_status
from web_fragments.fragment import Fragment
from webob.response import Response
from xblock.core import XBlock
from xblock.fields import Boolean, Scope, String

from ol_openedx_chat_xblock.constants import (
    ASK_TIM_TITLE_SYLLABUS,
    ASK_TIM_TITLE_TUTOR,
    CHAT_XBLOCK_BLOCK_ID,
    CHAT_XBLOCK_THREAD_ID,
    COOKIE_NAME_CHAT_XBLOCK,
    COOKIE_NAME_SYLLABUS_ANON,
    COOKIE_NAME_TUTOR_ANON,
    COURSE_ID_SUFFIX_TUTOR,
    INITIAL_MESSAGE_SYLLABUS,
    INITIAL_MESSAGE_TUTOR,
    PROBLEM_SET_INITIAL_MESSAGE_TUTOR,
    XBLOCK_TYPE_SYLLABUS,
    XBLOCK_TYPE_TUTOR,
)

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


def generate_canvas_course_id():
    """
    Generate a Canvas course ID from the LTI parameters.

    Returns:
        str: The generated Canvas course ID or an empty string.
    """
    # "lms.djangoapps.courseware.views.render_xblock()" method does not pass on the LTI
    # params upon an LTI launch. So we use get_current_request to get the current
    # running request to get the LTI params required to generate the Course ID.
    lti_request = get_current_request()

    if not lti_request:
        log.info("LTI launch request is missing or could not be retrieved.")
        return ""

    lti_params = {**lti_request.GET.dict(), **lti_request.POST.dict()}
    try:
        course_id = lti_params["custom_course_id"]
        context_label = lti_params["context_label"]
    except KeyError as e:
        missing_key = e.args[0]
        log.info(
            f"LTI launch request is missing the required parameter: '{missing_key}'."  # noqa: G004
        )
        return ""
    else:
        return f"{course_id}-{context_label}"


class OLChatXBlock(XBlock, StudioEditableXBlockMixin):
    """
    XBlock that enables OL AI Chat functionality in Open edX
    """

    display_name = String(
        display_name="Display Name",
        default="OL Chat XBlock",
        scope=Scope.settings,
        help="This name appears in the horizontal navigation at the top of the page.",
    )
    course_id = String(
        display_name="Course ID",
        default="",
        scope=Scope.settings,
        help="Course ID of the relevant course in Canvas",
    )
    learn_readable_course_id = String(
        default="",
        scope=Scope.user_state,
        help=(
            "Course ID of the relevant course in Canvas "
            "(Auto generates upon xBlock initialization)."
        ),
    )
    is_tutor_xblock = Boolean(
        display_name="Is Tutor xBlock?",
        default=False,
        scope=Scope.settings,
        help="Indicates if the xBlock is a tutor or syllabus xBlock",
    )

    editable_fields = (
        "display_name",
        "course_id",
        "is_tutor_xblock",
    )

    def get_xblock_chat_url(self):
        """
        Generate the URL for the AI chat.
        """
        return (
            settings.MIT_LEARN_AI_XBLOCK_TUTOR_CHAT_API_URL
            if self.is_tutor_xblock
            else settings.MIT_LEARN_AI_XBLOCK_CHAT_API_URL
        )

    def get_xblock_rating_url(self):
        """
        Generate the URL for the AI chat.
        """
        rating_url = self.runtime.handler_url(self, "ol_chat_rate")
        return f"{rating_url}/thread/:threadId/checkpoint/:checkpointPk/"

    def get_xblock_state(self):
        """
        Get the state of the xBlock.
        """
        return XBLOCK_TYPE_TUTOR if self.is_tutor_xblock else XBLOCK_TYPE_SYLLABUS

    def send_tracker_event(  # noqa: PLR0913
        self,
        event_name,
        value,
        canvas_course_id,
        problem_set=None,
        thread_id=None,
        checkpoint=None,
    ):
        """
        Send a tracker event.

        Args:
            event_name (str): The name of the event to track.
            value (str): The value to track.
            problem_set (str): The problem set title, if applicable.
        """
        tracker_payload = {
            "blockUsageKey": str(self.usage_key),
            "canvas_course_id": canvas_course_id,
            "xblock_state": self.get_xblock_state(),
            "value": value,
            "problem_set": problem_set,
        }
        if thread_id:
            tracker_payload["thread_id"] = thread_id
        if checkpoint:
            tracker_payload["checkpoint"] = checkpoint
        tracker.emit(f"{__package__}.{event_name}", tracker_payload)

    def get_problem_set_url(self):
        """
        Generate the URL for the problem set list.
        """
        base_url = settings.MIT_LEARN_AI_XBLOCK_PROBLEM_SET_LIST_URL.rstrip("/") + "/"

        params = {
            "run_readable_id": (self.course_id or self.learn_readable_course_id)
            + COURSE_ID_SUFFIX_TUTOR
        }

        return f"{base_url}?{urlencode(params)}"

    def get_learn_ai_rating_url(self, thread_id, checkpoint_id):
        """
        Generate the URL for the AI chat.
        """
        base_url = settings.MIT_LEARN_AI_XBLOCK_CHAT_RATING_URL.rstrip("/")
        return f"{base_url}/{thread_id}/messages/{checkpoint_id}/rate/"

    def get_ai_chat_init_js_args(self):
        """
        Generate the initialization arguments for the Smoot design AI Chat window.
        """
        init_payload = {
            "block_id": self.usage_key.block_id,
            "ask_tim_title": ASK_TIM_TITLE_SYLLABUS,
            "bot_initial_message": INITIAL_MESSAGE_SYLLABUS,
            "chat_rating_url": self.get_xblock_rating_url(),
        }
        if self.is_tutor_xblock:
            init_payload.update(
                {
                    "ask_tim_title": ASK_TIM_TITLE_TUTOR,
                    "problem_list_url": self.get_problem_set_url(),
                    "bot_initial_message": INITIAL_MESSAGE_TUTOR,
                    "problem_set_initial_message": PROBLEM_SET_INITIAL_MESSAGE_TUTOR,
                }
            )
        return init_payload

    def get_chat_thread_cookie_name(self):
        """Get the cookie key name for the chat session."""
        return (
            COOKIE_NAME_TUTOR_ANON
            if self.is_tutor_xblock
            else COOKIE_NAME_SYLLABUS_ANON
        )

    def validate_required_chat_api_params(self, course_id, message, problem_set_title):
        """Validate required parameters for the learn AI chat API."""
        if not course_id:
            log.info(
                "Course ID is not available in the xBlock. "
                "Falling back to auto-generated course ID from Canvas LTI."
            )
            if not self.learn_readable_course_id:
                log.info("Course ID is not available from Canvas LTI.")
                return "Course ID is required."
            log.info(
                "Using auto-generated course_id from LTI launch: %s",
                self.learn_readable_course_id,
            )
        if not message:
            log.error("Message field is required for chat.")
            return "Message field is required."
        if self.is_tutor_xblock and not problem_set_title:
            log.error("Problem set title is required for chat.")
            return "Problem set title is required."
        return None

    def student_view(self, context=None):  # noqa: ARG002
        """Render the student view of the block."""
        if not self.course_id:
            self.learn_readable_course_id = generate_canvas_course_id()

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
        fragment.initialize_js("OLChatBlock", json_args=self.get_ai_chat_init_js_args())
        return fragment

    def author_view(self, context=None):  # noqa: ARG002
        """
        Render the author view of the block.
        """
        if not self.course_id:
            self.learn_readable_course_id = generate_canvas_course_id()
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
        fragment.initialize_js("OLChatBlock", json_args=self.get_ai_chat_init_js_args())
        return fragment

    def validate_request(self, request):
        """
        Validate the incoming request.

        Args:
            request (Request): The incoming request object.

        Returns:
            Response: request_data if the request is valid otherwise error Response
        """
        try:
            request_data = request.json
        except Exception:  # noqa: BLE001
            log.warning("Invalid JSON in chat request.")
            return Response(
                "Invalid request body. Expected JSON.",
                status=api_status.HTTP_400_BAD_REQUEST,
            )
        return request_data

    def get_thread_and_block_ids_from_cookies(self, request):
        """
        Extract the thread ID and block ID from the cookies.

        Args:
            request (Request): The incoming request object.
        """
        req_chat_cookies = json.loads(
            request.cookies.get(COOKIE_NAME_CHAT_XBLOCK, "{}")
        )
        return (
            req_chat_cookies.get(CHAT_XBLOCK_THREAD_ID, None),
            req_chat_cookies.get(CHAT_XBLOCK_BLOCK_ID, None),
        )

    @XBlock.handler
    def ol_chat(self, request, suffix=""):  # noqa: ARG002
        """Start the chat session via external MIT LEARN AI API."""

        request_data = self.validate_request(request)
        if isinstance(request_data, Response):
            return request_data

        api_token = settings.MIT_LEARN_AI_XBLOCK_CHAT_API_TOKEN

        if not self.get_xblock_chat_url() or not api_token:
            log.error("Missing AI Chat API configuration (URL or token).")
            return Response(
                "Missing AI Chat API configurations. Please check your settings.",
                status=api_status.HTTP_400_BAD_REQUEST,
            )

        # Course ID will be used in this order of priority:
        # 1. The course_id field in the xBlock settings.
        # 2. The learn_readable_course_id field, which is auto-generated upon xBlock
        # initialization on LTI launch.
        # 3. If neither is available, it will return an error response.

        course_id_for_chat = self.course_id or self.learn_readable_course_id
        if self.is_tutor_xblock:
            course_id_for_chat += COURSE_ID_SUFFIX_TUTOR
        message = request_data.get("message", "").strip()
        problem_set_title = request_data.get("problem_set_title", "").strip()

        validation_error = self.validate_required_chat_api_params(
            course_id=course_id_for_chat,
            message=message,
            problem_set_title=problem_set_title,
        )
        if validation_error:
            return Response(
                validation_error,
                status=api_status.HTTP_400_BAD_REQUEST,
            )

        payload = {"message": message}

        if self.is_tutor_xblock:
            payload["run_readable_id"] = course_id_for_chat
            payload["problem_set_title"] = problem_set_title
        else:
            payload["collection_name"] = "content_files"
            payload["course_id"] = course_id_for_chat

        headers = {
            "Content-Type": "application/json",
            "canvas_token": api_token,
        }

        try:
            block_id = self.usage_key.block_id
            # Sending tracker event for request
            self.send_tracker_event(
                event_name="OLChat.submit",
                value=request_data.get("message", ""),
                canvas_course_id=course_id_for_chat,
                problem_set=problem_set_title,
            )

            # Use the cookies from the request to maintain session chat state
            req_chat_thread_id, req_block_id = (
                self.get_thread_and_block_ids_from_cookies(request)
            )
            # Reset the req_chat_thread_id cookie on different blocks to avoid
            # cross-block session issues.
            generated_ai_chat_cookies = {
                self.get_chat_thread_cookie_name(): req_chat_thread_id
                if req_block_id == block_id
                else None
            }

            response = requests.post(
                self.get_xblock_chat_url(),
                json=payload,
                headers=headers,
                timeout=60,
                cookies=generated_ai_chat_cookies,
            )

            # Check if the response was successful.
            response.raise_for_status()
            resp_ai_threads_anon = response.cookies.get(
                self.get_chat_thread_cookie_name(), None
            )
            xblock_response = Response(response.content)

            self.send_tracker_event(
                event_name="OLChat.response",
                value=str(response.content),
                canvas_course_id=course_id_for_chat,
                problem_set=problem_set_title,
            )

            # Set chat_xblock_thread_keys cookie for subsequent requests. This allows
            # using the same chat thread for a single xBlock.

            xblock_response.set_cookie(
                COOKIE_NAME_CHAT_XBLOCK,
                json.dumps(
                    {
                        CHAT_XBLOCK_THREAD_ID: resp_ai_threads_anon,
                        CHAT_XBLOCK_BLOCK_ID: block_id,
                    }
                ),
                httponly=True,
            )

            return xblock_response  # noqa: TRY300

        except requests.exceptions.RequestException:
            log.exception("Failed to contact MIT Learn AI service.")
            return Response(
                "Something went wrong while contacting the AI service.",
                status=api_status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            log.exception("An unexpected error occurred.")
            return Response(
                "An unexpected error occurred.",
                status=api_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @XBlock.handler
    def ol_chat_rate(self, request, suffix=""):
        """Submit feedback for chat to MIT LEARN AI API."""
        request_data = self.validate_request(request)
        course_id_for_chat = self.course_id or self.learn_readable_course_id
        if isinstance(request_data, Response):
            return request_data

        pattern = r"^/?thread/([^/]+)/checkpoint/(\d+)/$"
        # Match the suffix against the pattern
        match = re.match(pattern, suffix.strip())
        if not match:
            log.error(
                "Invalid URL. Expected /thread/<threadId>/checkpoint/<checkpointPk>"
            )
            return Response(
                "Invalid URL. Expected /thread/<threadId>/checkpoint/<checkpointPk>",
                status=api_status.HTTP_400_BAD_REQUEST,
            )

        thread_id, checkpoint_id = match.groups()
        api_token = settings.MIT_LEARN_AI_XBLOCK_CHAT_API_TOKEN

        if not settings.MIT_LEARN_AI_XBLOCK_CHAT_RATING_URL or not api_token:
            log.error(
                "Missing Chat rating API configuration (Chat Rating URL or API Token)."
            )
            return Response(
                "Missing Chat rating API configurations. Please check your settings.",
                status=api_status.HTTP_400_BAD_REQUEST,
            )

        headers = {"Content-Type": "application/json"}

        try:
            self.send_tracker_event(
                event_name="OLChat.rating.request",
                value=request_data.get("rating", ""),
                canvas_course_id=course_id_for_chat,
                checkpoint=checkpoint_id,
                thread_id=thread_id,
            )
            req_chat_thread_id, _ = self.get_thread_and_block_ids_from_cookies(request)

            generated_ai_chat_cookies = {
                self.get_chat_thread_cookie_name(): req_chat_thread_id
            }

            response = requests.post(
                self.get_learn_ai_rating_url(thread_id, checkpoint_id),
                json=request_data,
                headers=headers,
                timeout=60,
                cookies=generated_ai_chat_cookies,
            )

            # Check if the response was successful.
            response.raise_for_status()
            xblock_rating_response = Response(response.content)

            self.send_tracker_event(
                event_name="OLChat.rating.response",
                value=str(response.content),
                canvas_course_id=course_id_for_chat,
                checkpoint=checkpoint_id,
                thread_id=thread_id,
            )
            return xblock_rating_response  # noqa: TRY300

        except requests.exceptions.RequestException:
            log.exception("Failed to contact MIT Learn AI rating service.")
            return Response(
                "Something went wrong while contacting the AI service.",
                status=api_status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            log.exception("An unexpected error occurred.")
            return Response(
                "An unexpected error occurred.",
                status=api_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
