"""Production settings unique to the git auto export plugin."""

from ol_openedx_git_auto_export.constants import (
    ENABLE_AUTO_GITHUB_REPO_CREATION,
    ENABLE_GIT_AUTO_EXPORT,
)


def plugin_settings(settings):
    """Settings for the git auto export plugin."""  # noqa: D401
    settings.GIT_REPO_EXPORT_DIR = "/openedx/export_course_repos"
    settings.GITHUB_ORG_API_URL = "https://github.mit.edu/api/v3/orgs/mitodl"
    settings.GITHUB_ACCESS_TOKEN = "token"  # noqa: S105
    settings.FEATURES[ENABLE_GIT_AUTO_EXPORT] = True
    settings.FEATURES[ENABLE_AUTO_GITHUB_REPO_CREATION] = False
