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
        "MIT_LEARN_AI_XBLOCK_PROBLEM_SET_LIST_URL", ""
    )
    settings.MIT_LEARN_AI_XBLOCK_CHAT_RATING_URL = env_tokens.get(
        "MIT_LEARN_AI_XBLOCK_CHAT_RATING_URL", ""
    )
    settings.MIT_LEARN_AI_XBLOCK_CHAT_API_TOKEN = env_tokens.get(
        "MIT_LEARN_AI_XBLOCK_CHAT_API_TOKEN", ""
    )

    # Update the open edX filters with chat xBlock filters. We do not want to
    # override the existing ones, We just want to add ours in it.
    # NOTE: Remove this filter when Open edX upgrades MathJax to v3
    # (or equivalent to smoot-design)
    CHAT_XBLOCK_FILTERS = {
        "org.openedx.learning.xblock.render.started.v1": {
            "pipeline": ["ol_openedx_chat_xblock.filters.DisableMathJaxForOLChatBlock"],
            "fail_silently": False,
        }
    }
    existing_filters = env_tokens.get("OPEN_EDX_FILTERS_CONFIG", {})

    # Merge pipeline lists instead of overwriting
    for filter_name, config in CHAT_XBLOCK_FILTERS.items():
        if filter_name not in existing_filters:
            existing_filters[filter_name] = config
        else:
            existing_filters[filter_name]["pipeline"].extend(config.get("pipeline", []))
            # do not override fail_silently
            if "fail_silently" in config:
                existing_filters[filter_name].setdefault(
                    "fail_silently", config["fail_silently"]
                )

    settings.OPEN_EDX_FILTERS_CONFIG = existing_filters
