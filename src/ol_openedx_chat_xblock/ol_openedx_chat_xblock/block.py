import logging
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
    BOT_INITIAL_MESSAGE_DEFAULT,
    BOT_INITIAL_MESSAGE_TUTOR,
    CANVAS_TUTOR_COURSE_ID_PREFIX,
    PROBLEM_SET_INITIAL_MESSAGE_TUTOR,
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
        log.error("LTI launch request is missing or could not be retrieved.")
        return ""

    lti_params = {**lti_request.GET.dict(), **lti_request.POST.dict()}
    try:
        course_id = lti_params["custom_course_id"]
        context_label = lti_params["context_label"]
    except KeyError as e:
        missing_key = e.args[0]
        log.error(  # noqa: TRY400
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
        help="Indicates if the xBlock is a tutor xBlock",
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

    def get_xblock_state(self):
        """
        Get the state of the xBlock.
        """
        return "Tutor" if self.is_tutor_xblock else "Syllabus"

    def send_tracker_event(self, event_name, value, problem_set=None):
        """
        Send a tracker event.

        Args:
            event_name (str): The name of the event to track.
            value (str): The value to track.
            problem_set (str): The problem set title, if applicable.
        """
        tracker.emit(
            f"{__package__}.{event_name}",
            {
                "blockUsageKey": str(self.usage_key),
                "canvas_course_id": self.course_id,
                "xblock_state": self.get_xblock_state(),
                "value": value,
                "problem_set": problem_set,
            },
        )

    def get_problem_set_url(self):
        """
        Generate the URL for the problem set list.
        """
        return (
            settings.MIT_LEARN_AI_XBLOCK_PROBLEM_SET_LIST_URL
            + (
                "?"
                if settings.MIT_LEARN_AI_XBLOCK_PROBLEM_SET_LIST_URL.endswith("/")
                else "/?"
            )
            + urlencode(
                {
                    "run_readable_id": (self.course_id or self.learn_readable_course_id)
                    + CANVAS_TUTOR_COURSE_ID_PREFIX
                }
            )
        )

    def get_ai_chat_init_js_args(self):
        """
        Generate the initialization arguments for the Smoot design AI Chat window.
        """
        init_payload = {
            "block_id": self.usage_key.block_id,
            "ask_tim_title": ASK_TIM_TITLE_SYLLABUS,
            "bot_initial_message": BOT_INITIAL_MESSAGE_DEFAULT,
        }
        if self.is_tutor_xblock:
            init_payload["ask_tim_title"] = ASK_TIM_TITLE_TUTOR
            init_payload["problem_list_url"] = self.get_problem_set_url()
            init_payload["bot_initial_message"] = BOT_INITIAL_MESSAGE_TUTOR
            init_payload["problem_set_initial_message"] = (
                PROBLEM_SET_INITIAL_MESSAGE_TUTOR
            )
        return init_payload

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

    @XBlock.handler
    def ol_chat(self, request, suffix=""):  # noqa: ARG002, PLR0911, C901
        """Start the chat session via external MIT LEARN AI API."""
        try:
            request_data = request.json
        except Exception:  # noqa: BLE001
            log.warning("Invalid JSON in chat request.")
            return Response(
                "Invalid request body. Expected JSON.",
                status=api_status.HTTP_400_BAD_REQUEST,
            )

        api_token = settings.MIT_LEARN_AI_XBLOCK_CHAT_API_TOKEN

        if not self.get_xblock_chat_url() or not api_token:
            log.error("Missing AI API configuration (URL or token).")
            return Response(
                "Missing API configurations. Please check your settings.",
                status=api_status.HTTP_400_BAD_REQUEST,
            )

        # Course ID will be used in this order of priority:
        # 1. The course_id field in the xBlock settings.
        # 2. The learn_readable_course_id field, which is auto-generated upon xBlock
        # initialization on LTI launch.
        # 3. If neither is available, it will return an error response.
        course_id_for_chat = self.course_id
        if not course_id_for_chat:
            log.info(
                "Course ID is not available in the XBlock. "
                "Falling back to auto-generated course ID from Canvas LTI."
            )
            if not self.learn_readable_course_id:
                log.error("Course ID is not available from Canvas LTI.")
                return Response(
                    "Course ID is required.",
                    status=api_status.HTTP_400_BAD_REQUEST,
                )
            log.info(
                "Using auto-generated course_id: %s", self.learn_readable_course_id
            )
            course_id_for_chat = self.learn_readable_course_id

        message = request_data.get("message", "").strip()
        problem_set_title = request_data.get("problem_set_title", "").strip()

        if not message:
            log.error("Message field is required for chat.")
            return Response(
                "Message field is required.",
                status=api_status.HTTP_400_BAD_REQUEST,
            )

        payload = {"message": message}

        if self.is_tutor_xblock:
            payload["run_readable_id"] = (
                course_id_for_chat + CANVAS_TUTOR_COURSE_ID_PREFIX
            )
            if not problem_set_title:
                log.error("Problem set title is required for tutor xBlock.")
                return Response(
                    "Problem set title is required for tutor xBlock.",
                    status=api_status.HTTP_400_BAD_REQUEST,
                )
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
                event_name="f{__package__}.OLChat.submit",
                value=request_data.get("message", ""),
                problem_set=problem_set_title,
            )

            # Use the cookies from the request to maintain session state
            # This is important for the MIT Learn AI service to track user sessions
            req_syllabusbot_ai_threads_anon = request.cookies.get(
                "SyllabusBot_ai_threads_anon", None
            )
            req_block_id = request.cookies.get("block_id", None)

            # If the incoming request's block_id does not match the current block_id,
            # reset the SyllabusBot_ai_threads_anon cookie to avoid cross-block session
            # issues. This ensures that each xBlock maintains its own chat session.
            if req_block_id != block_id:
                req_syllabusbot_ai_threads_anon = None

            req_cookies = {
                "SyllabusBot_ai_threads_anon": req_syllabusbot_ai_threads_anon
            }
            response = requests.post(
                self.get_xblock_chat_url(),
                json=payload,
                headers=headers,
                timeout=60,
                cookies=req_cookies,
            )

            # Check if the response was successful.
            response.raise_for_status()
            resp_syllabusbot_ai_threads_anon = response.cookies.get(
                "SyllabusBot_ai_threads_anon"
            )
            xblock_response = Response(response.content)

            # Sending tracker event for response
            self.send_tracker_event(
                event_name=f"{__package__}.OLChat.response",
                value=str(response.content),
                problem_set=problem_set_title,
            )

            # Set SyllabusBot_ai_threads_anon cookie in the response so that it can be
            # used in subsequent requests. This will allow using the same chat thread
            # for a single xBlock.
            xblock_response.set_cookie(
                "SyllabusBot_ai_threads_anon",
                resp_syllabusbot_ai_threads_anon,
                httponly=True,
            )
            xblock_response.set_cookie("block_id", block_id, httponly=True)
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
