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

    # Username of the service worker the webhook consumer uses to create its own
    # enrollments through the Open edX enrollment REST API. Enrollments created
    # by this user are not sent back to the consumer. When unset, every
    # enrollment triggers a webhook.
    settings.ENROLLMENT_WEBHOOK_SERVICE_WORKER_USERNAME = None

    # Settings for the Certificate Webhook
    # Webhook URL used to request certificate creation after course completion.
    settings.CERTIFICATE_WEBHOOK_URL = None
    # OAuth access token for the certificate webhook.
    settings.CERTIFICATE_WEBHOOK_ACCESS_TOKEN = None
