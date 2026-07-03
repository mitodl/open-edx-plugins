# noqa: INP001

"""Helper to register the chat xBlock render filter.

Shared by the common, devstack, and production settings so the pipeline step is
declared once. Production must re-apply it because ``lms``/``cms`` production
settings overwrite ``OPEN_EDX_FILTERS_CONFIG`` wholesale from the deployment YAML
(``vars().update(...)``), which drops any entry registered only in common settings.
"""

XBLOCK_RENDER_STARTED_FILTER = "org.openedx.learning.xblock.render.started.v1"
CHAT_XBLOCK_PIPELINE_STEP = (
    "ol_openedx_chat_xblock.filters.DisableMathJaxForOLChatBlock"
)


def register_chat_xblock_filter(settings):
    """Merge the chat xBlock render step into ``OPEN_EDX_FILTERS_CONFIG``.

    Idempotent and preserves other configured filters and pipeline steps (e.g.
    other plugins contributing to the same render.started filter).
    """
    filters_config = getattr(settings, "OPEN_EDX_FILTERS_CONFIG", {}) or {}
    filter_entry = filters_config.setdefault(
        XBLOCK_RENDER_STARTED_FILTER, {"fail_silently": False, "pipeline": []}
    )
    filter_entry.setdefault("pipeline", [])
    if CHAT_XBLOCK_PIPELINE_STEP not in filter_entry["pipeline"]:
        filter_entry["pipeline"].append(CHAT_XBLOCK_PIPELINE_STEP)
    settings.OPEN_EDX_FILTERS_CONFIG = filters_config
