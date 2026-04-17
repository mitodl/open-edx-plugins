"""Common settings for AI Static Translations plugin."""


def apply_common_settings(settings):
    """
    Apply custom settings for the AI Static Translations plugin.

    These settings are shared with ol_openedx_course_translations.
    If that plugin is also installed, its settings take precedence
    since both plugins configure the same keys.
    """
    if not hasattr(settings, "TRANSLATIONS_PROVIDERS"):
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
    if not hasattr(settings, "TRANSLATIONS_GITHUB_TOKEN"):
        settings.TRANSLATIONS_GITHUB_TOKEN = ""
    if not hasattr(settings, "TRANSLATIONS_REPO_URL"):
        settings.TRANSLATIONS_REPO_URL = (
            "https://github.com/mitodl/mitxonline-translations.git"
        )
    if not hasattr(settings, "TRANSLATIONS_REPO_PATH"):
        settings.TRANSLATIONS_REPO_PATH = ""
    if not hasattr(settings, "LITE_LLM_REQUEST_TIMEOUT"):
        settings.LITE_LLM_REQUEST_TIMEOUT = 300  # seconds
