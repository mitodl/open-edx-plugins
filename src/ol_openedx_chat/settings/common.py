# noqa: INP001

"""Settings to provide to edX"""


def plugin_settings(settings):
    """
    Populate common settings
    """
    env_tokens = getattr(settings, "ENV_TOKENS", {})
    settings.MIT_LEARN_AI_API_URL = env_tokens.get("MIT_LEARN_AI_API_URL", "")
    settings.MIT_LEARN_API_BASE_URL = env_tokens.get("MIT_LEARN_API_BASE_URL", "")
    settings.MIT_LEARN_SUMMARY_FLASHCARD_URL = env_tokens.get(
        "MIT_LEARN_SUMMARY_FLASHCARD_URL", ""
    )
