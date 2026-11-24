"""Common settings for the ol-openedx-video-thumbnail-copy plugin."""


def plugin_settings(settings):
    """Set defaults for the video thumbnail copy plugin."""
    # Public base URL of the source instance's media storage, e.g.
    # https://xpro-production-edxapp-storage.s3.amazonaws.com/media/
    settings.OL_VIDEO_THUMBNAIL_COPY_SOURCE_BASE_URL = None
