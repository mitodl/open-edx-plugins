# noqa: INP001

"""Settings to provide to edX"""


def plugin_settings(settings):
    """
    Populate common settings
    """
    env_tokens = getattr(settings, "ENV_TOKENS", {})
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = env_tokens.get(
        "ENABLE_AUTO_LANGUAGE_SELECTION",
        False,
    )
    settings.AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS = env_tokens.get(
        "AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS",
        ["admin", "sysadmin", "instructor"],
    )
    settings.DEEPL_API_KEY = env_tokens.get("DEEPL_API_KEY", "")
    settings.OL_OPENEDX_COURSE_TRANSLATIONS_TARGET_DIRECTORIES = env_tokens.get(
        "OL_OPENEDX_COURSE_TRANSLATIONS_TARGET_DIRECTORIES",
        [
            "about",
            "course",
            "chapter",
            "html",
            "info",
            "problem",
            "sequential",
            "vertical",
            "video",
            "static",
            "tabs",
        ],
    )
    settings.OL_OPENEDX_COURSE_TRANSLATIONS_SUPPORTED_ARCHIVE_EXTENSIONS = (
        env_tokens.get(
            "OL_OPENEDX_COURSE_TRANSLATIONS_SUPPORTED_ARCHIVE_EXTENSIONS",
            [".tar.gz", ".tgz", ".tar"],
        )
    )
    settings.OL_OPENEDX_COURSE_TRANSLATIONS_TRANSLATABLE_EXTENSIONS = env_tokens.get(
        "OL_OPENEDX_COURSE_TRANSLATIONS_TRANSLATABLE_EXTENSIONS",
        [".html", ".xml", ".srt"],
    )
