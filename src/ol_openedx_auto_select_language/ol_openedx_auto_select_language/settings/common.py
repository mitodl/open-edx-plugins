# noqa: INP001

"""Common settings for LMS and CMS to provide to edX"""


def apply_common_settings(settings):
    """
    Apply custom settings function for LMS and CMS settings.

    Args:
        settings: Django settings object to modify
    """
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = False
    settings.AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS = ["admin", "sysadmin", "instructor"]
