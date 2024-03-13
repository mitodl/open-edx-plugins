"""Settings to provide to edX"""


def plugin_settings(settings):
    """
    Populate settings
    """
    settings.EVENT_TRACKING_BACKENDS['rapid_response'] = {
        'ENGINE': 'rapid_response_xblock.logger.SubmissionRecorder',
        'OPTIONS': {
            'name': 'rapid_response',
        }
    }

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
