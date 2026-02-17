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
    # Translation repository settings (used by sync_and_translate_language command)
    # Git URL of the translations repository (e.g. mitxonline-translations).
    settings.TRANSLATIONS_REPO_URL = (
        "https://github.com/mitodl/mitxonline-translations.git"
    )
    # Local path to a clone of the translations repo; leave empty to clone
    # at the default path from TRANSLATIONS_REPO_URL.
    settings.TRANSLATIONS_REPO_PATH = ""
    settings.LITE_LLM_REQUEST_TIMEOUT = 300  # seconds

    # HTML/XML translation safety/perf knobs (LLM providers only)
    settings.LLM_HTMLXML_MAX_UNITS_PER_REQUEST = 40
    settings.LLM_HTMLXML_MAX_CHARS_PER_REQUEST = 6000
    settings.LLM_HTMLXML_MAX_CHARS_PER_UNIT = 800
    settings.LLM_TRANSLATION_CACHE_MAX_ENTRIES = 5000

    settings.TRANSLATE_FILE_TASK_LIMITS = {
        "soft_time_limit": 29 * 60,  # 29 minutes
        "time_limit": 30 * 60,  # 30 minutes (hard kill)
        "max_retries": 1,  # 1 Initial try + 1 retry = 2 attempts
        "retry_countdown": 1 * 60,  # wait 1m before retry
    }

    # Base directory where translate_course extracts archives and writes
    # translated .tar.gz output. Directory is created at runtime if missing.
    settings.COURSE_TRANSLATIONS_BASE_DIR = "/openedx/data/course_translations/"

    settings.COURSE_TRANSLATIONS_SUPPORTED_LANGUAGES = {
        "ar": "Arabic",
        "de": "German",
        "de_DE": "German (Germany)",
        "el": "Greek",
        "en": "English",
        "es": "Spanish",
        "es_419": "Spanish (Latin America)",
        "fr": "French",
        "hi": "Hindi",
        "ja": "Japanese",
        "pt": "Portuguese",
        "pt_BR": "Portuguese (Brazil)",
        "ru": "Russian",
        "zh": "Chinese",
        "zh_HANS": "Chinese (Simplified)",
        "zh_HANT": "Chinese (Traditional)",
    }
