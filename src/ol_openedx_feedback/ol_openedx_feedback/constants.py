"""Constants for ol_openedx_feedback."""

# Default structural/container blocks that never get a feedback trigger.
# Deployments can override this via the
# ``OL_OPENEDX_FEEDBACK_EXCLUDED_BLOCK_TYPES`` Django setting (e.g. to also
# exclude a content type like ``html``).
DEFAULT_EXCLUDED_BLOCK_TYPES = {"course", "chapter", "sequential", "vertical"}

# Block types that render a title the learner can see, mapped to the field
# holding it. An unlisted type sends no title and the panel names the type
# instead. A wrong entry leaks an author-only Studio name, so when in doubt
# leave it out — see "Visible titles" in the README before editing.
DEFAULT_VISIBLE_TITLE_FIELDS = {
    "annotatable": "display_name",
    "drag-and-drop-v2": "display_name",
    "edx_sga": "display_name",
    "lti": "display_name",
    "lti_consumer": "display_name",
    "pdf": "display_name",
    "poll": "display_name",
    "problem": "display_name",
    "staffgradedxblock": "display_name",
    "video": "display_name",
    "videoalpha": "display_name",
    "word_cloud": "display_name",
    "openassessment": "title",
    "survey": "block_name",
}

# Types whose title renders only when an author-controlled boolean is on.
TITLE_VISIBILITY_TOGGLES = {"drag-and-drop-v2": "show_title"}

# Show the "Feedback" text label next to the icon. Off by default (icon only).
DEFAULT_SHOW_LABEL = False
