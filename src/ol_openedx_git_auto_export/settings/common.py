"""Common settings unique to the git auto export plugin."""

from ol_openedx_git_auto_export.constants import ENABLE_GIT_AUTO_EXPORT


def plugin_settings(settings):
    """Settings for the git auto export plugin."""  # noqa: D401
    settings.GIT_REPO_EXPORT_DIR = "/openedx/export_course_repos"
    settings.FEATURES[ENABLE_GIT_AUTO_EXPORT] = True
