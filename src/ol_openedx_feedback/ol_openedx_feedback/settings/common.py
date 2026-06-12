"""Settings to provide to edX"""


def plugin_settings(settings):
    """Populate common settings for ol_openedx_feedback."""
    # Maximum length allowed for a feedback comment.
    settings.OL_FEEDBACK_COMMENT_MAX_LENGTH = 1000
