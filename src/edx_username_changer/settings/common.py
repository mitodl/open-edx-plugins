# noqa: INP001

"""Settings to provide to edX"""


def plugin_settings(settings):
    """
    Populate common settings
    """
    env_tokens = getattr(settings, "ENV_TOKENS", {})

    # .. setting_name: ENABLE_EDX_USERNAME_CHANGER
    # .. setting_default: False
    # .. setting_description: Enable/Disable the username changer plugin

    settings.ENABLE_EDX_USERNAME_CHANGER = env_tokens.get(
        "ENABLE_EDX_USERNAME_CHANGER", False
    )
