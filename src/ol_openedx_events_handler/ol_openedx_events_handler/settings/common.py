"""Common plugin settings for the OL Open edX events handler plugin."""


def plugin_settings(settings):
    """
    Default settings applied to both LMS and CMS configurations.
    """

    # URL of the webhook endpoint for course access role enrollment.
    settings.ENROLLMENT_WEBHOOK_URL = None

    # OAuth access token for the enrollment webhook.
    settings.ENROLLMENT_WEBHOOK_ACCESS_TOKEN = None

    # Course access roles that should trigger the enrollment webhook.
    settings.ENROLLMENT_COURSE_ACCESS_ROLES = ["instructor", "staff"]
