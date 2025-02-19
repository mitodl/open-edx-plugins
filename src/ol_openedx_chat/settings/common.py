# noqa: INP001

"""Settings to provide to edX"""


def plugin_settings(settings):
    """
    Populate common settings
    """
    env_tokens = getattr(settings, "ENV_TOKENS", {})

    # .. setting_name: OL_CHAT_SETTINGS
    # .. setting_default: {}
    # .. setting_description: A dictionary containing the LLM model names as dictionary
    #   keys and model API tokens/keys as values. This dictionary keys would be
    #   as LLM model names in the chat settings form in CMS.
    #
    #   A sample setting would look like:
    # .. {"MODEL_NAME1": API_KEY, "MODEL_NAME2": API_KEY}

    settings.OL_CHAT_SETTINGS = env_tokens.get("OL_CHAT_SETTINGS", {})
    settings.LEARN_AI_API_URL = env_tokens.get("LEARN_AI_API_URL", "")
