# noqa: INP001

"""Settings to provide to edX"""


def plugin_settings(settings):
    """
    Populate common settings
    """
    env_tokens = getattr(settings, "ENV_TOKENS", {})
    settings.LEARN_AI_API_URL = env_tokens.get("LEARN_AI_API_URL", "")
