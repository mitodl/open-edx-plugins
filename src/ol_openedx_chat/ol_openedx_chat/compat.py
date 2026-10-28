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


# .. toggle_name: ol_openedx_chat.contact_us_enabled
# .. toggle_implementation: CourseWaffleFlag
# .. toggle_default: False
# .. toggle_description: Shows the Contact us launcher in the Open edX MFEs.
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2026-10-28
# .. toggle_tickets: https://github.com/mitodl/hq/issues/14033
# .. toggle_warning: None.
CONTACT_US_ENABLED = "contact_us_enabled"


def get_contact_us_enabled_flag():
    """
    Import and return Waffle flag for showing the Contact us launcher.
    """
    from openedx.core.djangoapps.waffle_utils import CourseWaffleFlag  # noqa: PLC0415

    return CourseWaffleFlag(f"{WAFFLE_FLAG_NAMESPACE}.{CONTACT_US_ENABLED}", __name__)
