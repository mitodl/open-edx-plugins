# noqa: INP001
"""Settings to provide to edX"""


def plugin_settings(settings):
    """
    Populate CMS settings
    """
    settings.ENABLE_RAPID_RESPONSE_AUTHOR_VIEW = False


DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
