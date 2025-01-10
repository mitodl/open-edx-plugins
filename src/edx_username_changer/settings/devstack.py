# noqa: INP001

"""Settings to provide to edX"""


def plugin_settings(settings):
    """
    Populate devstack settings
    """
    settings.ENABLE_EDX_USERNAME_CHANGER = False
