# noqa: INP001

"""Production settings to provide to edX"""

from ol_openedx_auto_select_language.settings.filters import (
    register_video_language_filter,
)


def plugin_settings(settings):
    """
    Populate production (lms) settings
    """
    # Re-register the video-language render filter. Production overwrites
    # OPEN_EDX_FILTERS_CONFIG wholesale from the deployment YAML, dropping the
    # entry added by common settings; this merges the pipeline step back in.
    register_video_language_filter(settings)
