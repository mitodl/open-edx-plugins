"""Constants for ol_openedx_feedback."""

# Structural/container blocks never get a feedback trigger; everything else does.
EXCLUDED_BLOCK_TYPES = {"course", "chapter", "sequential", "vertical"}
