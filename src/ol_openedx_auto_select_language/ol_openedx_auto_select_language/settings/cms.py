# noqa: INP001

"""Settings to provide to edX"""

from ol_openedx_auto_select_language.settings.common import apply_common_settings


def plugin_settings(settings):
    """
    Populate cms settings
    """
    apply_common_settings(settings)
    settings.MIDDLEWARE.extend(
        [
            "ol_openedx_auto_select_language.middleware.CourseLanguageCookieResetMiddleware"
        ]
    )
