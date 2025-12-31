# noqa: INP001

"""Common settings for LMS and CMS to provide to edX"""


def apply_common_settings(settings):
    """
    Apply custom settings function for LMS and CMS settings.
    """
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = False
    settings.AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS = ["admin", "sysadmin", "instructor"]
    settings.DEEPL_API_KEY = ""
    settings.OPENAI_API_KEY = ""
    settings.ANTHROPIC_API_KEY = ""
    settings.MISTRAL_API_KEY = ""
    settings.GOOGLE_API_KEY = ""
    settings.GITHUB_TOKEN = ""
    # Translation repository settings
    settings.REPO_PATH = ""
    settings.REPO_URL = "https://github.com/mitodl/mitxonline-translations.git"
    # Default LLM model for translations
    settings.DEFAULT_MODEL = "mistral/mistral-large-latest"
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
