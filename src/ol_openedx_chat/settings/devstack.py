# noqa: INP001

"""Settings to provide to edX"""


def plugin_settings(settings):
    """
    Populate devstack settings
    """
    settings.OL_CHAT_SETTINGS = {"GPT1": "TEST", "GPT2": "123", "GPT3": ""}
