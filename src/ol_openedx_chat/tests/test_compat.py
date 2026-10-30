"""Tests for ol_openedx_chat waffle flag accessors."""

from ol_openedx_chat.compat import (
    get_contact_us_enabled_flag,
    get_ol_openedx_chat_enabled_flag,
)


def test_contact_us_flag_name():
    """The Contact us flag is namespaced under the plugin and distinctly named."""
    assert get_contact_us_enabled_flag().name == "ol_openedx_chat.contact_us_enabled"


def test_contact_us_flag_is_separate_from_chat_flag():
    """The launcher and the xBlock aside must toggle independently."""
    assert get_contact_us_enabled_flag().name != get_ol_openedx_chat_enabled_flag().name
