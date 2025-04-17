# noqa: INP001

"""Settings to provide to edX"""


def plugin_settings(settings):
    """
    Populate common settings
    """
    env_tokens = getattr(settings, "ENV_TOKENS", {})

    # .. toggle_name: FEATURES['ENABLE_EDX_USERNAME_CHANGER']
    # .. toggle_implementation: DjangoSetting
    # .. toggle_default: False
    # .. toggle_description: Enable the username changer feature
    # .. toggle_use_case: open_edx
    # .. toggle_creation_date: 2025-01-15

    settings.FEATURES["ENABLE_EDX_USERNAME_CHANGER"] = env_tokens.get(
        "FEATURES", {}
    ).get("ENABLE_EDX_USERNAME_CHANGER", False)
