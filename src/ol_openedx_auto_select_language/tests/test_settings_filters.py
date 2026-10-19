"""Tests for filter registration helpers."""

from ol_openedx_auto_select_language.settings.filters import (
    RESTRICT_TRANSCRIPTS_PIPELINE_STEP,
    VERTICAL_CHILD_RENDER_STARTED_FILTER,
    register_restrict_transcripts_filter,
)


class _Settings:
    """Minimal stand-in for the Django settings object."""


def test_registers_pipeline_step():
    settings = _Settings()

    register_restrict_transcripts_filter(settings)

    entry = settings.OPEN_EDX_FILTERS_CONFIG[VERTICAL_CHILD_RENDER_STARTED_FILTER]
    assert entry["pipeline"] == [RESTRICT_TRANSCRIPTS_PIPELINE_STEP]
    assert entry["fail_silently"] is False


def test_is_idempotent_and_preserves_other_steps():
    settings = _Settings()
    settings.OPEN_EDX_FILTERS_CONFIG = {
        VERTICAL_CHILD_RENDER_STARTED_FILTER: {
            "fail_silently": False,
            "pipeline": ["other.plugin.Step"],
        }
    }

    register_restrict_transcripts_filter(settings)
    register_restrict_transcripts_filter(settings)

    entry = settings.OPEN_EDX_FILTERS_CONFIG[VERTICAL_CHILD_RENDER_STARTED_FILTER]
    assert entry["pipeline"] == [
        "other.plugin.Step",
        RESTRICT_TRANSCRIPTS_PIPELINE_STEP,
    ]
