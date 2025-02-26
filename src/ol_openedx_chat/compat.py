"""
Compatibility layer to isolate core-platform method calls from implementation.
"""

WAFFLE_FLAG_NAMESPACE = "ol_openedx_chat"

# .. toggle_name: ol_openedx_chat.enable_ol_openedx_chat
# .. toggle_implementation: CourseWaffleFlag
# .. toggle_default: False
# .. toggle_description: Enables ol_openedx_chat plugin for a course.
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2025-02-26
# .. toggle_tickets: None
# .. toggle_warning: None.
ENABLE_OL_OPENEDX_CHAT = "enable_ol_openedx_chat"


def get_enable_ol_openedx_chat_flag():
    """
    Import and return Waffle flag for enabling ol_openedx_chat.
    """
    from openedx.core.djangoapps.waffle_utils import CourseWaffleFlag

    return CourseWaffleFlag(f"{WAFFLE_FLAG_NAMESPACE}.enable_ol_openedx_chat", __name__)
