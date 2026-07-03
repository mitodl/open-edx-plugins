# noqa: INP001

"""Production settings to provide to edX"""

from ol_openedx_chat_xblock.settings.filters import register_chat_xblock_filter


def plugin_settings(settings):
    """
    Populate production settings
    """
    # Re-register the chat xBlock render filter. Production overwrites
    # OPEN_EDX_FILTERS_CONFIG wholesale from the deployment YAML, dropping the
    # entry added by common settings; this merges the pipeline step back in.
    register_chat_xblock_filter(settings)
