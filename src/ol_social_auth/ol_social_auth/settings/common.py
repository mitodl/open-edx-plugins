from __future__ import annotations

from typing import Any


def _load_env_tokens(app_settings) -> dict[str, Any]:
    return getattr(
        app_settings,
        "ENV_TOKENS",
        {},
    )


PIPELINE_SUBSTITUTIONS = {
    "social_core.pipeline.social_auth.social_user": (
        "ol_social_auth.actions.debug_social_user"
    ),
}


def _substitute_debug_pipeline(app_settings):
    pipeline = app_settings.SOCIAL_AUTH_PIPELINE

    app_settings.SOCIAL_AUTH_PIPELINE = [
        PIPELINE_SUBSTITUTIONS.get(action, action) for action in pipeline
    ]


def plugin_settings(app_settings):
    env_tokens = _load_env_tokens(app_settings)
    social_auth_debug = env_tokens.get("SOCIAL_AUTH_DEBUG", False)

    if social_auth_debug:
        _substitute_debug_pipeline(app_settings)
