# noqa: INP001

"""Settings to provide to edX"""


def plugin_settings(settings):
    """
    Populate common settings
    """
    env_tokens = getattr(settings, "ENV_TOKENS", {})
    settings.MIT_APP_CERTIFICATE_CREATION_URL = env_tokens.get(
        "MIT_APP_CERTIFICATE_GENERATION_URL", ""
    )
    settings.MIT_APP_ENROLLMENT_CREATION_URL = env_tokens.get(
        "MIT_APP_ENROLLMENT_CREATION_URL", ""
    )
    settings.MIT_APP_API_KEY = env_tokens.get("MIT_APP_API_KEY", "")
