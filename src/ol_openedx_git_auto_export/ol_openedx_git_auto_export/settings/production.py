"""Production settings unique to the git auto export plugin."""

from ol_openedx_git_auto_export.constants import (
    ENABLE_AUTO_GITHUB_REPO_CREATION,
    ENABLE_GIT_AUTO_EXPORT,
)


def plugin_settings(settings):
    """Settings for the git auto export plugin."""  # noqa: D401
    env_tokens = getattr(settings, "ENV_TOKENS", {})
    settings.GIT_REPO_EXPORT_DIR = env_tokens.get(
        "GIT_REPO_EXPORT_DIR", "/openedx/export_course_repos"
    )
    settings.GITHUB_ORG_API_URL = env_tokens.get("GITHUB_ORG_API_URL", "")
    settings.GITHUB_ACCESS_TOKEN = env_tokens.get("GITHUB_ACCESS_TOKEN")
    settings.FEATURES[ENABLE_GIT_AUTO_EXPORT] = env_tokens.get("FEATURES", {}).get(
        ENABLE_GIT_AUTO_EXPORT, True
    )
    settings.FEATURES[ENABLE_AUTO_GITHUB_REPO_CREATION] = env_tokens.get(
        "FEATURES", {}
    ).get(ENABLE_AUTO_GITHUB_REPO_CREATION, False)
