"""Tests for the canvas integration plugin's production settings."""

from __future__ import annotations

from types import SimpleNamespace

from ol_openedx_canvas_integration.settings.lms import production


def _app_settings(**env_tokens):
    """Build a minimal settings namespace for ``plugin_settings``."""
    return SimpleNamespace(
        AUTH_TOKENS={},
        ENV_TOKENS=env_tokens,
        CANVAS_ACCESS_TOKEN=None,
        CANVAS_BASE_URL=None,
        CANVAS_COURSE_ID_CACHE_TIMEOUT=300,
        OPEN_EDX_FILTERS_CONFIG={},
        TEMPLATES=[{"DIRS": []}],
    )


class TestCanvasCourseIdCacheTimeout:
    """Tests for ``CANVAS_COURSE_ID_CACHE_TIMEOUT`` coercion in production settings."""

    def test_defaults_when_key_absent(self):
        app_settings = _app_settings()
        production.plugin_settings(app_settings)
        assert app_settings.CANVAS_COURSE_ID_CACHE_TIMEOUT == 300  # noqa: PLR2004

    def test_string_override_is_coerced_to_int(self):
        app_settings = _app_settings(CANVAS_COURSE_ID_CACHE_TIMEOUT="600")
        production.plugin_settings(app_settings)
        assert app_settings.CANVAS_COURSE_ID_CACHE_TIMEOUT == 600  # noqa: PLR2004

    def test_explicit_none_override_falls_back_to_default(self):
        app_settings = _app_settings(CANVAS_COURSE_ID_CACHE_TIMEOUT=None)
        production.plugin_settings(app_settings)
        assert app_settings.CANVAS_COURSE_ID_CACHE_TIMEOUT == 300  # noqa: PLR2004

    def test_int_override_is_kept(self):
        app_settings = _app_settings(CANVAS_COURSE_ID_CACHE_TIMEOUT=900)
        production.plugin_settings(app_settings)
        assert app_settings.CANVAS_COURSE_ID_CACHE_TIMEOUT == 900  # noqa: PLR2004
