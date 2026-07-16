# noqa: INP001

"""Settings to provide to edX"""

from ol_openedx_feedback.constants import DEFAULT_EXCLUDED_BLOCK_TYPES


def plugin_settings(settings):
    """
    Populate common settings
    """
    env_tokens = getattr(settings, "ENV_TOKENS", {})
    settings.OL_OPENEDX_FEEDBACK_EXCLUDED_BLOCK_TYPES = set(
        env_tokens.get(
            "OL_OPENEDX_FEEDBACK_EXCLUDED_BLOCK_TYPES",
            DEFAULT_EXCLUDED_BLOCK_TYPES,
        )
    )
