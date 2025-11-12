# noqa: INP001

"""Settings to provide to edX"""


def plugin_settings(settings):
    """
    Populate devstack settings
    """
    env_tokens = getattr(settings, "ENV_TOKENS", {})
    settings.DEEPL_API_KEY = env_tokens.get("DEEPL_API_KEY", "")
