"""Constants for ol_openedx_feedback."""

# Default structural/container blocks that never get a feedback trigger.
# Deployments can override this via the
# ``OL_OPENEDX_FEEDBACK_EXCLUDED_BLOCK_TYPES`` Django setting (e.g. to also
# exclude a content type like ``html``).
DEFAULT_EXCLUDED_BLOCK_TYPES = {"course", "chapter", "sequential", "vertical"}
