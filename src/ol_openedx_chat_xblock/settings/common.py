# noqa: INP001

"""Settings to provide to edX"""


def plugin_settings(settings):
    """
    Populate common settings
    """
    env_tokens = getattr(settings, "ENV_TOKENS", {})
    settings.MIT_LEARN_AI_XBLOCK_CHAT_API_URL = env_tokens.get(
        "MIT_LEARN_AI_XBLOCK_CHAT_API_URL", ""
    )
    settings.MIT_LEARN_AI_XBLOCK_CHAT_API_TOKEN = env_tokens.get(
        "MIT_LEARN_AI_XBLOCK_CHAT_API_TOKEN", ""
    )
