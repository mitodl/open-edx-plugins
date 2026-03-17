"""Tests for ol_social_auth tasks."""

from ol_social_auth import tasks


def test_clear_expired_tokens(mocker):
    """Test that clear_expired_tokens calls the clear_expired function."""
    patched_clear_expired = mocker.patch("ol_social_auth.tasks.clear_expired")

    tasks.clear_expired_tokens.delay()
    patched_clear_expired.assert_called_once_with()


def test_clear_expired_tokens_logging(mocker):
    """Test that clear_expired_tokens logs start and finish messages."""
    mocker.patch("ol_social_auth.tasks.clear_expired")
    patched_log_info = mocker.patch("ol_social_auth.tasks.log.info")

    tasks.clear_expired_tokens()

    assert patched_log_info.call_count == 2
    patched_log_info.assert_any_call("Starting clear_expired_tokens...")
    patched_log_info.assert_any_call("Finished clear_expired_tokens.")
