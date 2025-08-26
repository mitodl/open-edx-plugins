# noqa: INP001

"""Settings to provide to edX"""


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
        "MIT_LEARN_AI_XBLOCK_PROBLEM_LIST_URL", ""
    )
    settings.MIT_LEARN_AI_XBLOCK_CHAT_API_TOKEN = env_tokens.get(
        "MIT_LEARN_AI_XBLOCK_CHAT_API_TOKEN", ""
    )
    settings.OPEN_EDX_FILTERS_CONFIG = {
        "org.openedx.learning.xblock.render.started.v1": {
            "pipeline": ["ol_openedx_chat_xblock.filters.DisableMathJaxForOLChatBlock"],
            "fail_silently": False,
        }
    }
