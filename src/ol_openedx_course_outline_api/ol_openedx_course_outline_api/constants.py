"""
Constants for the Course Outline API plugin.
"""

# Block type groupings used when summarizing course content.
CONTENT_TYPES = {"course", "chapter", "sequential", "vertical"}
KNOWN_LEAF_TYPES = {"video", "html", "problem"}

# When format is this value (or empty), the subsection is not linked to an assignment.
NOT_GRADED_FORMAT = "notgraded"

# Keys the Blocks API may use for staff-only visibility.
# The Blocks API serializer returns visible_to_staff_only, backed by
# VisibilityTransformer.MERGED_VISIBLE_TO_STAFF_ONLY in the block structure.
# Some environments may expose the merged field name directly, so we check both.
VISIBLE_TO_STAFF_ONLY_KEYS = ("visible_to_staff_only", "merged_visible_to_staff_only")

# Schema version embedded in the cache key.
# Increment this when the response shape or computation logic changes so old cache
# entries won't be reused.
COURSE_OUTLINE_CACHE_SCHEMA_VERSION = 1
