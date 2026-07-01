"""Compatibility layer isolating core-platform imports."""

WAFFLE_FLAG_NAMESPACE = "ol_openedx_feedback"

# .. toggle_name: ol_openedx_feedback.feedback_enabled
# .. toggle_implementation: CourseWaffleFlag
# .. toggle_default: False
# .. toggle_description: Enables the per-block feedback trigger for a course.
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2026-06-09
OL_OPENEDX_FEEDBACK_ENABLED = "feedback_enabled"


def get_feedback_enabled_flag():
    """Return the CourseWaffleFlag controlling feedback rollout."""
    from openedx.core.djangoapps.waffle_utils import CourseWaffleFlag  # noqa: PLC0415

    return CourseWaffleFlag(
        f"{WAFFLE_FLAG_NAMESPACE}.{OL_OPENEDX_FEEDBACK_ENABLED}", __name__
    )
