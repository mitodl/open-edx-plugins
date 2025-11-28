# noqa: INP001

"""Settings to provide to edX"""


def plugin_settings(settings):
    """
    Populate common settings
    """
    env_tokens = getattr(settings, "ENV_TOKENS", {})
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
