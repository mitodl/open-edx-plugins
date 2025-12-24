# noqa: INP001

"""Common settings for LMS and CMS to provide to edX"""


def apply_common_settings(settings):
    """
    Apply custom settings function for LMS and CMS settings.
    """
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = False
    settings.AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS = ["admin", "sysadmin", "instructor"]
    settings.DEEPL_API_KEY = ""
    settings.COURSE_TRANSLATIONS_TARGET_DIRECTORIES = [
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
    ]
    settings.COURSE_TRANSLATIONS_SUPPORTED_ARCHIVE_EXTENSIONS = [
        ".tar.gz",
        ".tgz",
        ".tar",
    ]
    settings.COURSE_TRANSLATIONS_TRANSLATABLE_EXTENSIONS = [
        ".html",
        ".xml",
        ".srt",
    ]
