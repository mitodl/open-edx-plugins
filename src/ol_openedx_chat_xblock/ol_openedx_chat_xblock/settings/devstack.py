# noqa: INP001

"""Settings to provide to edX"""

from ol_openedx_chat_xblock.settings.filters import register_chat_xblock_filter


def plugin_settings(settings):
    """
    Populate devstack settings
    """
    env_tokens = getattr(settings, "ENV_TOKENS", {})
    settings.MIT_LEARN_AI_XBLOCK_CHAT_API_URL = env_tokens.get(
        "MIT_LEARN_AI_XBLOCK_CHAT_API_URL", ""
    )
    settings.MIT_LEARN_AI_XBLOCK_TUTOR_CHAT_API_URL = env_tokens.get(
        "MIT_LEARN_AI_XBLOCK_TUTOR_CHAT_API_URL", ""
    )
    settings.MIT_LEARN_AI_XBLOCK_PROBLEM_SET_LIST_URL = env_tokens.get(
        "MIT_LEARN_AI_XBLOCK_PROBLEM_SET_LIST_URL", ""
    )
    settings.MIT_LEARN_AI_XBLOCK_CHAT_RATING_URL = env_tokens.get(
        "MIT_LEARN_AI_XBLOCK_CHAT_RATING_URL", ""
    )
    settings.MIT_LEARN_AI_XBLOCK_CHAT_API_TOKEN = env_tokens.get(
        "MIT_LEARN_AI_XBLOCK_CHAT_API_TOKEN", ""
    )

    # Register the chat xBlock render filter (adds to any existing pipeline).
    # NOTE: Remove this filter when Open edX upgrades MathJax to v3
    # (or equivalent to smoot-design)
    register_chat_xblock_filter(settings)
