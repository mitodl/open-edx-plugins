"""Tests for ol_social_auth tasks."""

from ol_social_auth import tasks


def test_ol_clear_expired_tokens(mocker):
    """Test that ol_clear_expired_tokens calls the clear_expired function."""
    patched_clear_expired = mocker.patch("ol_social_auth.tasks.clear_expired")

    tasks.ol_clear_expired_tokens.delay()
    patched_clear_expired.assert_called_once_with()


def test_ol_clear_expired_tokens_logging(mocker):
    """Test that ol_clear_expired_tokens logs start and finish messages."""
    mocker.patch("ol_social_auth.tasks.clear_expired")
    patched_log_info = mocker.patch("ol_social_auth.tasks.log.info")

    tasks.ol_clear_expired_tokens()

    expected_log_call_count = 2
    assert patched_log_info.call_count == expected_log_call_count  # noqa: S101
    patched_log_info.assert_any_call("Starting ol_clear_expired_tokens...")
    patched_log_info.assert_any_call("Finished ol_clear_expired_tokens.")
