# noqa: INP001

"""Common settings for LMS and CMS to provide to edX"""

import logging

from ol_openedx_course_translations.utils.constants import PROVIDER_AZURE

logger = logging.getLogger(__name__)


def apply_common_settings(settings):
    """
    Apply custom settings function for LMS and CMS settings.

    Configures translation-related settings including supported file types,
    translation providers, and repository settings.

    Args:
        settings: Django settings object to modify
    """
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
    settings.COURSE_TRANSLATIONS_TRANSLATABLE_EXTENSIONS = [
        ".html",
        ".xml",
        ".srt",
    ]
    # Relative to ``course/`` directory.
    settings.COURSE_TRANSLATIONS_UPDATES_ITEMS_JSON_RELATIVE_PATH = (
        "info/updates.items.json"
    )
    settings.TRANSLATIONS_PROVIDERS = {
        "default_provider": "mistral",
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

    # Base directory for course translations.
    settings.COURSE_TRANSLATIONS_BASE_DIR = "/openedx/data/course_translations/"

    settings.COURSE_TRANSLATIONS_SUPPORTED_LANGUAGES = {
        "ar": "Arabic",
        "de": "German",
        "de_DE": "German (Germany)",
        "el": "Greek",
        "en": "English",
        "es_ES": "Spanish (Spain)",
        "es_419": "Spanish (Latin America)",
        "fr": "French",
        "hi": "Hindi",
        "ja": "Japanese",
        "pt": "Portuguese",
        "pt_BR": "Portuguese (Brazil)",
        "ru": "Russian",
        "sw": "Swahili",
        "zh": "Chinese",
        "zh_HANS": "Chinese (Simplified)",
        "zh_HANT": "Chinese (Traditional)",
    }

    apply_azure_openai_settings(settings)


def apply_azure_openai_settings(settings):
    """
    Add an ``azure`` entry to TRANSLATIONS_PROVIDERS from the AZURE_OPENAI_* settings.

    The deployment delivers Azure OpenAI configuration as flat top-level
    settings in its own config file rather than as part of
    TRANSLATIONS_PROVIDERS, because the config files are concatenated rather
    than merged, and a second TRANSLATIONS_PROVIDERS key would silently replace
    the one holding the other providers. Folding them in here leaves every
    other provider entry as it was. Does nothing unless AZURE_OPENAI_ENDPOINT
    is set.

    Args:
        settings: Django settings object to modify
    """
    endpoint = getattr(settings, "AZURE_OPENAI_ENDPOINT", None)
    if not endpoint:
        return
    api_version = getattr(settings, "AZURE_OPENAI_API_VERSION", None)
    deployment = getattr(settings, "AZURE_OPENAI_DEFAULT_DEPLOYMENT", None)
    missing = [
        name
        for name, value in (
            ("AZURE_OPENAI_API_VERSION", api_version),
            ("AZURE_OPENAI_DEFAULT_DEPLOYMENT", deployment),
        )
        if not value
    ]
    # A partial Azure config must not stop LMS/CMS from starting over one
    # translation provider; leave azure unregistered and say why.
    if missing:
        logger.warning(
            "AZURE_OPENAI_ENDPOINT is set but %s is not; "
            "the azure translation provider is not registered",
            ", ".join(missing),
        )
        return
    settings.TRANSLATIONS_PROVIDERS = {
        **settings.TRANSLATIONS_PROVIDERS,
        PROVIDER_AZURE: {
            "api_base": endpoint,
            "api_version": api_version,
            "default_model": deployment,
        },
    }
