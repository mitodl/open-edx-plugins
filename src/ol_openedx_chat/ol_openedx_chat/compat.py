"""
Compatibility layer to isolate core-platform method calls from implementation.
"""

WAFFLE_FLAG_NAMESPACE = "ol_openedx_chat"

# .. toggle_name: ol_openedx_chat.ol_openedx_chat_enabled
# .. toggle_implementation: CourseWaffleFlag
# .. toggle_default: False
# .. toggle_description: Enables ol_openedx_chat plugin for a course.
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2025-02-26
# .. toggle_tickets: None
# .. toggle_warning: None.
OL_OPENEDX_CHAT_ENABLED = "ol_openedx_chat_enabled"


def get_ol_openedx_chat_enabled_flag():
    """
    Import and return Waffle flag for enabling ol_openedx_chat.
    """
    from openedx.core.djangoapps.waffle_utils import CourseWaffleFlag  # noqa: PLC0415

    return CourseWaffleFlag(
        f"{WAFFLE_FLAG_NAMESPACE}.{OL_OPENEDX_CHAT_ENABLED}", __name__
    )
