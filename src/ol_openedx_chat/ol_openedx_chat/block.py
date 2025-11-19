import logging
from urllib.parse import quote as urlquote

import pkg_resources
from django.conf import settings
from django.template import Context, Template
from django.utils.translation import gettext_lazy as _
from eventtracking import tracker
from rest_framework import status as api_status
from web_fragments.fragment import Fragment
from webob.response import Response
from xblock.core import XBlock, XBlockAside
from xblock.fields import Boolean, Scope

try:
    from xmodule.modulestore.xml import (
        XMLImportingModuleStoreRuntime as XMLImportingModuleStoreRuntime,  # noqa: PLC0414
    )
except ImportError:
    from xmodule.modulestore.xml import ImportSystem as XMLImportingModuleStoreRuntime

try:
    from xmodule.video_block.transcripts_utils import (
        Transcript,
        get_available_transcript_languages,
    )
except ImportError:
    from openedx.core.djangoapps.video_config.transcripts_utils import (
        Transcript,
        get_available_transcript_languages,
    )
from xmodule.x_module import AUTHOR_VIEW, STUDENT_VIEW

from ol_openedx_chat.compat import get_ol_openedx_chat_enabled_flag
from ol_openedx_chat.constants import (
    ENGLISH_LANGUAGE_TRANSCRIPT,
    MIT_AI_CHAT_URL_PATHS,
    PROBLEM_BLOCK_CATEGORY,
    TUTOR_INITIAL_MESSAGES,
    VIDEO_BLOCK_CATEGORY,
)
from ol_openedx_chat.utils import (
    is_aside_applicable_to_block,
    is_ol_chat_enabled_for_course,
)

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


class OLChatAside(XBlockAside):
    """
    XBlock aside that enables OL AI Chat functionality for an XBlock
    """

    ol_chat_enabled = Boolean(
        display_name=_("Open Learning Chat enabled status"),
        default=True,
        scope=Scope.settings,
        help=_("Indicates whether or not Open Learning chat is enabled for a block"),
    )

    @XBlockAside.aside_for(STUDENT_VIEW)
    def student_view_aside(self, block, context=None):
        """
        Renders the aside contents for the student view
        """  # noqa: D401

        # This is a workaround for those blocks which do not have has_author_view=True
        # because when a block does not define has_author_view=True in it, the only view
        # that gets rendered is student_view in place of author view.

        if getattr(self.runtime, "is_author_mode", False):
            return self.author_view_aside(block, context)

        fragment = Fragment("")
        block_usage_key = block.usage_key
        block_id = block_usage_key.block_id
        block_type = getattr(block, "category", None)

        if not self.ol_chat_enabled:
            return fragment

        fragment.add_content(
            render_template(
                "static/html/student_view.html",
                {
                    "block_id": block_id,
                    "block_usage_key": block_usage_key,
                    "block_type": block_type,
                },
            )
        )
        fragment.add_css(get_resource_bytes("static/css/ai_chat.css"))
        fragment.add_javascript(get_resource_bytes("static/js/ai_chat.js"))

        request_body = {
            "edx_module_id": block_usage_key,
        }

        if block_type == PROBLEM_BLOCK_CATEGORY:
            request_body["block_siblings"] = [
                sibling.usage_key for sibling in block.get_parent().get_children()
            ]

        if block_type == VIDEO_BLOCK_CATEGORY:
            try:
                transcripts_info = block.get_transcripts_info()
                if transcripts_info.get("transcripts", {}).get(
                    ENGLISH_LANGUAGE_TRANSCRIPT
                ):
                    request_body["transcript_asset_id"] = Transcript.asset_location(
                        block.location,
                        transcripts_info["transcripts"][ENGLISH_LANGUAGE_TRANSCRIPT],
                    )
                else:
                    transcript_languages = get_available_transcript_languages(
                        block.edx_video_id
                    )
                    if ENGLISH_LANGUAGE_TRANSCRIPT in transcript_languages:
                        request_body["transcript_asset_id"] = Transcript.asset_location(
                            block.location,
                            f"{block.edx_video_id}-{ENGLISH_LANGUAGE_TRANSCRIPT}.srt",
                        )

            except Exception:  # noqa: BLE001
                log.info(
                    "Error while fetching transcripts for block %s",
                    block.location,
                )

        extra_context = {
            "block_id": block_id,
            "learning_mfe_base_url": settings.LEARNING_MICROFRONTEND_URL,
            "drawer_payload": {
                "blockUsageKey": str(block_usage_key),
                "trackingUrl": f"{settings.LMS_ROOT_URL}{self.runtime.handler_url(self, 'track_user_events')}",  # noqa: E501
                "blockType": block_type,
                # Frontend will style AskTIM slightly
                "title": f"AskTIM about {block.display_name}",
                "chat": {
                    "chatId": block_id,
                    "initialMessages": TUTOR_INITIAL_MESSAGES,
                    "apiUrl": f"{settings.MIT_LEARN_AI_API_URL}/{MIT_AI_CHAT_URL_PATHS[block_type]}",  # noqa: E501
                    "requestBody": request_body,
                    "userId": self.runtime.user_id,
                },
            },
        }

        if block_type == VIDEO_BLOCK_CATEGORY and request_body.get(
            "transcript_asset_id"
        ):
            url_quoted_transcript_id = urlquote(
                str(request_body["transcript_asset_id"])
            )
            content_url = f"{settings.MIT_LEARN_SUMMARY_FLASHCARD_URL}?edx_module_id={url_quoted_transcript_id}"  # noqa: E501
            extra_context["drawer_payload"].update(
                {
                    "summary": {
                        "apiUrl": content_url,
                    }
                }
            )

        fragment.initialize_js("AiChatAsideInit", json_args=extra_context)
        return fragment

    @XBlockAside.aside_for(AUTHOR_VIEW)
    def author_view_aside(self, block, context=None):  # noqa: ARG002
        """
        Renders the aside contents for the author view
        """  # noqa: D401
        fragment = Fragment("")
        fragment.add_content(
            render_template(
                "static/html/studio_view.html",
                {
                    "is_enabled": self.ol_chat_enabled,
                    "block_id": block.location.block_id,  # Passing this along as a unique key for checkboxes  # noqa: E501
                },
            )
        )
        fragment.add_css(get_resource_bytes("static/css/studio.css"))
        fragment.add_javascript(get_resource_bytes("static/js/studio.js"))
        fragment.initialize_js("OLChatInit")
        return fragment

    @classmethod
    def should_apply_to_block(cls, block):
        """
        Overrides base XBlockAside implementation. Indicates whether or not this aside
        should apply to a given block.

        Due to the different ways that the Studio and LMS runtimes construct XBlock
        instances, the problem type of the given block needs to be retrieved in
        different ways.
        """  # noqa: D401
        # During the course import, this method is called and the block is not
        # updated with the course information where it is being imported.
        # In that case, we cannot check for the course settings and waffle flag.
        # We only check for the block type. For normal CMS and LMS flows, it will
        # check for the course settings and waffle flag.
        if isinstance(block.runtime, XMLImportingModuleStoreRuntime):
            return is_aside_applicable_to_block(block=block)

        return (
            get_ol_openedx_chat_enabled_flag().is_enabled(
                block.scope_ids.usage_id.context_key
            )
            and is_aside_applicable_to_block(block=block)
            and is_ol_chat_enabled_for_course(block=block)
        )

    @XBlock.handler
    def update_chat_config(self, request, suffix=""):  # noqa: ARG002
        """Update the chat configurations"""
        try:
            posted_data = request.json
        except ValueError:
            return Response(
                "Invalid request body", status=api_status.HTTP_400_BAD_REQUEST
            )

        self.ol_chat_enabled = posted_data.get("is_enabled", True)
        return Response()

    @XBlock.handler
    def track_user_events(self, request, suffix=""):  # noqa: ARG002
        """
        Track user events by emitting them to the event tracker.
        """
        request_data = request.json
        tracker.emit(
            request_data.get("event_type", ""), request_data.get("event_data", {})
        )
        return Response()
