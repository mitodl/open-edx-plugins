"""
Constants for the Course Outline API plugin.
"""

# Block type groupings used when summarizing course content.
CONTAINER_TYPES = {"course", "chapter", "sequential", "vertical"}
KNOWN_LEAF_TYPES = {"video", "html", "problem"}

# When format is this value (or empty), the subsection is not linked to an assignment.
NOT_GRADED_FORMAT = "notgraded"

# Keys the Blocks API may use for staff-only visibility.
# The Blocks API serializer returns visible_to_staff_only, backed by
# VisibilityTransformer.MERGED_VISIBLE_TO_STAFF_ONLY in the block structure.
# Some environments may expose the merged field name directly, so we check both.
VISIBLE_TO_STAFF_ONLY_KEYS = ("visible_to_staff_only", "merged_visible_to_staff_only")

# Per-course response cache (used only when include_gating is False; key = course_id).
COURSE_OUTLINE_CACHE_KEY_PREFIX = "ol_course_outline_api:outline:v0:"
COURSE_OUTLINE_CACHE_TIMEOUT_SECONDS = 300  # 5 minutes
