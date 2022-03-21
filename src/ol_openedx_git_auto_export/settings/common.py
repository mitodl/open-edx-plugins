"""Common settings unique to the git auto export plugin."""


def plugin_settings(settings):
    """Settings for the git auto export plugin."""
    settings.GIT_REPO_EXPORT_DIR = "/edx/var/edxapp/export_course_repos"
    settings.FEATURES["ENABLE_GIT_AUTO_EXPORT"] = True
