"""Constants for ol_openedx_feedback."""

# Structural/container blocks never get a feedback trigger; everything else does.
EXCLUDED_BLOCK_TYPES = {"course", "chapter", "sequential", "vertical"}

# Tracking event name emitted on each submission (flows to the data platform).
FEEDBACK_SUBMITTED_EVENT = "edx.block.feedback.submitted"
