import pkg_resources
from django.conf import settings
from django.template import Context, Template
from django.utils.translation import gettext_lazy as _
from ol_openedx_chat.utils import is_aside_applicable_to_block
from rest_framework import status as api_status
from web_fragments.fragment import Fragment
from webob.response import Response
from xblock.core import XBlock, XBlockAside
from xblock.fields import Boolean, Scope, String
from xmodule.x_module import AUTHOR_VIEW, STUDENT_VIEW


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
        default=False,
        scope=Scope.settings,
        help=_("Indicates whether or not Open Learning chat is enabled for a block"),
    )
    chat_prompts = String(
        display_name=_("Open Learning Chat Prompt text"),
        default="",
        scope=Scope.settings,
        help=_("Prompt hint text for chat in a block"),
    )
    additional_solution = String(
        display_name=_("Additional solution for problem"),
        default="",
        scope=Scope.settings,
        help=_("Additional solution for the problem in context of chat"),
    )
    llm_model = String(
        display_name=_("Open Learning Chat selected LLM model"),
        default="",
        scope=Scope.settings,
        help=_("Selected LLM model to be used for a block"),
    )
    ask_tim_drawer_title = String(
        display_name=_("Open Learning Drawer Title"),
        default="",
        scope=Scope.settings,
        help=_("Drawer title displayed in the chat drawer"),
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
        if not self.ol_chat_enabled:
            return fragment

        fragment.add_content(
            render_template(
                "static/html/student_view.html",
                {
                    "block_key": self.scope_ids.usage_id.usage_key.block_id,
                    "block_type": getattr(block, "category", None),
                },
            )
        )
        fragment.add_css(get_resource_bytes("static/css/ai_chat.css"))
        fragment.add_javascript(get_resource_bytes("static/js/ai_chat.js"))
        extra_context = {
            "starters": self.chat_prompts.split("\n") if self.chat_prompts else [],
            "ask_tim_drawer_title": self.ask_tim_drawer_title,
            "block_usage_key": self.scope_ids.usage_id.usage_key.block_id,
            "user_id": self.runtime.user_id,
            "learn_ai_api_url": settings.LEARN_AI_API_URL,
            "learning_mfe_base_url": settings.LEARNING_MICROFRONTEND_URL,
        }

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
                    "chat_prompts": self.chat_prompts,
                    "ask_tim_drawer_title": self.ask_tim_drawer_title
                    if self.ask_tim_drawer_title
                    else f"about {block.display_name}",
                    "selected_llm_model": self.llm_model,
                    "additional_solution": self.additional_solution,
                    "llm_models_list": list(
                        settings.OL_CHAT_SETTINGS
                    ),  # Converting dict keys into a list
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
        return is_aside_applicable_to_block(block=block)

    @XBlock.handler
    def update_chat_config(self, request, suffix=""):  # noqa: ARG002
        """Update the chat configurations"""
        try:
            posted_data = request.json
        except ValueError:
            return Response(
                "Invalid request body", status=api_status.HTTP_400_BAD_REQUEST
            )

        self.chat_prompts = posted_data.get("chat_prompts", "")
        self.ask_tim_drawer_title = posted_data.get("ask_tim_drawer_title", "")
        self.llm_model = posted_data.get("selected_llm_model", "")
        self.ol_chat_enabled = posted_data.get("is_enabled", False)
        self.additional_solution = posted_data.get("additional_solution", "")
        return Response()
