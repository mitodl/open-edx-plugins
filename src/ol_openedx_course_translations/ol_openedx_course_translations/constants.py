"""Constants for course translations."""

# Provider names
PROVIDER_DEEPL = "deepl"
PROVIDER_OPENAI = "openai"
PROVIDER_GEMINI = "gemini"
PROVIDER_MISTRAL = "mistral"

# DeepL API constants
DEEPL_MAX_PAYLOAD_SIZE = 128000  # 128KB limit
DEEPL_ENABLE_BETA_LANGUAGES = True

# Language code mappings for DeepL API
DEEPL_LANGUAGE_CODES = {
    "fr": "FR",
    "de": "DE",
    "es": "ES",
    "pt": "PT-PT",
    "pt-br": "PT-BR",
    "hi": "HI",
    "ar": "AR",
    "zh": "ZH",
    "kr": "KO",
    "ja": "JA",
    "id": "ID",
    "ru": "RU",
    "el": "EL",
    "tr": "TR",
    "sq": "SQ",
}

# Human-readable language names for LLM prompts
LANGUAGE_DISPLAY_NAMES = {
    "en": "English",
    "de": "Deutsch",
    "es": "Español",
    "fr": "Français",
    "pt-br": "Português - Brasil",
    "ru": "Русский",
    "hi": "हिंदी",
    "el": "ελληνικά",
    "ja": "日本語",
    "ar": "العربية",
    "zh": "中文",
    "tr": "Türkçe",
    "sq": "Shqip",
    "kr": "한국어",
    "id": "Bahasa Indonesia",
}

# LLM error detection keywords
LLM_ERROR_KEYWORDS = [
    "token",
    "quota",
    "limit",
    "too large",
    "context_length_exceeded",
    "503",
    "timeout",
]

# LLM explanation phrases to filter from responses
LLM_EXPLANATION_KEYWORDS = [
    "here is",
    "here's",
    "translation:",
    "translated text:",
    "note:",
    "explanation:",
    "i have translated",
    "i've translated",
]

# Translation markers for structured responses
TRANSLATION_MARKER_START = ":::TRANSLATION_START:::"
TRANSLATION_MARKER_END = ":::TRANSLATION_END:::"

# Archive and file size limits
TAR_FILE_SIZE_LIMIT = 512 * 1024 * 1024  # 512MB

# Task configuration
TASK_TIMEOUT_SECONDS = 600  # 10 minutes
TASK_POLL_INTERVAL_SECONDS = 2
