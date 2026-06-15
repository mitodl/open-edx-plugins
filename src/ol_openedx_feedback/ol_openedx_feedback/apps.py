"""ol_openedx_feedback Django application initialization."""

from django.apps import AppConfig


class OLOpenedxFeedbackConfig(AppConfig):
    """Configuration for the ol_openedx_feedback Django application.

    Aside-only plugin: the feedback trigger is registered via the
    ``xblock_asides.v1`` entry point. There are no URLs, models, or settings —
    feedback is persisted in learn-ai, and the MFE owns the submit URL.
    """

    name = "ol_openedx_feedback"
    verbose_name = "Open edX Block Feedback"

    plugin_app = {}
