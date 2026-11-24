"""Production settings for the ol-openedx-video-thumbnail-copy plugin."""


def plugin_settings(settings):
    """Read the source base URL from the environment's YAML config, if set."""
    env_tokens = getattr(settings, "ENV_TOKENS", {})
    settings.OL_VIDEO_THUMBNAIL_COPY_SOURCE_BASE_URL = env_tokens.get(
        "OL_VIDEO_THUMBNAIL_COPY_SOURCE_BASE_URL",
        settings.OL_VIDEO_THUMBNAIL_COPY_SOURCE_BASE_URL,
    )
