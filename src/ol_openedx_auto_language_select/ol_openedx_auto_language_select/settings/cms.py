# noqa: INP001

"""Settings to provide to edX"""

from ol_openedx_auto_language_select.settings.common import apply_common_settings


def plugin_settings(settings):
    """
    Populate cms settings
    """
    apply_common_settings(settings)
    settings.MIDDLEWARE.extend(
        [
            "ol_openedx_auto_language_select.middleware.CourseLanguageCookieResetMiddleware"
        ]
    )
