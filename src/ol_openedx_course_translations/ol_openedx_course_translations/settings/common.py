# noqa: INP001

"""Common settings for LMS and CMS to provide to edX"""


def apply_common_settings(settings):
    """
    Apply custom settings function for LMS and CMS settings.

    Configures translation-related settings including language selection,
    supported file types, translation providers, and repository settings.

    Args:
        settings: Django settings object to modify
    """
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = False
    settings.AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS = ["admin", "sysadmin", "instructor"]
    settings.COURSE_TRANSLATIONS_TARGET_DIRECTORIES = [
        "about",
        "course",
        "chapter",
        "drafts",
        "html",
        "info",
        "policies",
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
    settings.TRANSLATIONS_PROVIDERS = {
        "default_provider": "mistral",
        "deepl": {
            "api_key": "",
        },
        "openai": {
            "api_key": "",
            "default_model": "gpt-5.2",
        },
        "gemini": {
            "api_key": "",
            "default_model": "gemini-3-pro-preview",
        },
        "mistral": {
            "api_key": "",
            "default_model": "mistral-large-latest",
        },
    }
    settings.TRANSLATIONS_GITHUB_TOKEN = ""
    # Translation repository settings
    settings.TRANSLATIONS_REPO_PATH = ""
    settings.TRANSLATIONS_REPO_URL = (
        "https://github.com/mitodl/mitxonline-translations.git"
    )
    settings.LITE_LLM_REQUEST_TIMEOUT = 300  # seconds

    # HTML/XML translation safety/perf knobs (LLM providers only)
    settings.LLM_HTMLXML_MAX_UNITS_PER_REQUEST = 40
    settings.LLM_HTMLXML_MAX_CHARS_PER_REQUEST = 6000
    settings.LLM_HTMLXML_MAX_CHARS_PER_UNIT = 800
    settings.LLM_TRANSLATION_CACHE_MAX_ENTRIES = 5000

    settings.TRANSLATE_FILE_TASK_LIMITS = {
        "soft_time_limit": 9 * 60,  # 9 minutes
        "time_limit": 10 * 60,  # 10 minutes (hard kill)
        "max_retries": 1,  # 1 Initial try + 1 retry = 2 attempts
        "retry_countdown": 1 * 60,  # wait 1m before retry
    }
