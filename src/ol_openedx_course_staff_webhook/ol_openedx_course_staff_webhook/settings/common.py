"""Common plugin settings for the course staff webhook plugin."""


def plugin_settings(settings):
    """
    Default settings for the MITx Online integration plugin.

    These are applied to both LMS and CMS configurations.
    """
    # URL of the MITx Online webhook endpoint for course staff enrollment.
    settings.MITXONLINE_WEBHOOK_URL = None

    # API key / Bearer token for authenticating with the MITx Online webhook.
    settings.MITXONLINE_WEBHOOK_KEY = None

    # Course access roles that should trigger the MITx Online enrollment webhook.
    settings.MITXONLINE_COURSE_STAFF_ROLES = ["instructor", "staff"]
