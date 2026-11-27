"""App configuration for the ol-openedx-video-thumbnail-copy plugin."""

from django.apps import AppConfig


class OLOpenEdxVideoThumbnailCopyConfig(AppConfig):
    """App configuration for the ol-openedx-video-thumbnail-copy plugin."""

    name = "ol_openedx_video_thumbnail_copy"
    verbose_name = "OL Open edX Video Thumbnail Copy"

    # Empty, but it must be set: edx-django-utils skips apps without plugin_app
    # when building INSTALLED_APPS, and then the command isn't found.
    plugin_app: dict = {}
