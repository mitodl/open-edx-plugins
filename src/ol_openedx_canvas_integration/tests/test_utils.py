from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
from django.http import Http404

from ol_openedx_canvas_integration import utils

CANVAS_COURSE_ID_1 = 12345
CANVAS_COURSE_ID_2 = 9999


@pytest.mark.parametrize(
    ("course", "expected"),
    [
        pytest.param(None, None, id="course_is_none"),
        pytest.param(
            SimpleNamespace(other_course_settings={}),
            None,
            id="canvas_id_not_set",
        ),
        pytest.param(
            SimpleNamespace(other_course_settings={"canvas_id": CANVAS_COURSE_ID_1}),
            CANVAS_COURSE_ID_1,
            id="canvas_id_set",
        ),
        pytest.param(
            SimpleNamespace(
                other_course_settings={
                    "canvas_id": CANVAS_COURSE_ID_2,
                    "other_setting": "value",
                    "another_setting": 123,
                }
            ),
            CANVAS_COURSE_ID_2,
            id="canvas_id_with_other_settings",
        ),
    ],
)
def test_get_canvas_course_id(course, expected):
    """Test that get_canvas_course_id returns canvas_id from course settings, or None.

    None is returned when the course is None or canvas_id is absent from settings.
    """
    assert utils.get_canvas_course_id(course=course) == expected


@pytest.mark.parametrize(
    ("task_output", "expected"),
    [
        pytest.param(
            {},
            "0 grades and 0 assignments updated or created",
            id="no_results_key",
        ),
        pytest.param(
            {"results": {}},
            "0 grades and 0 assignments updated or created",
            id="empty_results",
        ),
        pytest.param(
            {"results": {"assignments": 5}},
            "0 grades and 5 assignments updated or created",
            id="only_assignments",
        ),
        pytest.param(
            {"results": {"grades": 10}},
            "10 grades and 0 assignments updated or created",
            id="only_grades",
        ),
        pytest.param(
            {"results": {"grades": 15, "assignments": 3}},
            "15 grades and 3 assignments updated or created",
            id="grades_and_assignments",
        ),
        pytest.param(
            {
                "results": {
                    "grades": 25,
                    "assignments": 7,
                    "other_field": "ignored",
                    "another_field": 99,
                }
            },
            "25 grades and 7 assignments updated or created",
            id="additional_fields_ignored",
        ),
        pytest.param(
            {"results": {"grades": 0, "assignments": 0}},
            "0 grades and 0 assignments updated or created",
            id="zero_counts",
        ),
        pytest.param(
            {"results": {"grades": 1000, "assignments": 500}},
            "1000 grades and 500 assignments updated or created",
            id="high_counts",
        ),
    ],
)
def test_get_task_output_formatted_message(task_output, expected):
    """Test that formatted message correctly reports grade and assignment counts."""
    assert utils.get_task_output_formatted_message(task_output) == expected


_CACHE_MISS = object()


class StubCache:
    """Cache stub that captures get and set operations."""

    def __init__(self, get_value=_CACHE_MISS):
        """Initialize cache hit value (defaults to a miss) and call capture lists."""
        self.get_value = get_value
        self.get_calls = []
        self.set_calls = []

    def get(self, key, default=None):
        """Record cache get lookups; return the configured value, or default on miss."""
        self.get_calls.append(key)
        return default if self.get_value is _CACHE_MISS else self.get_value

    def set(self, key, value, timeout=None):
        """Record cache set operations."""
        self.set_calls.append((key, value, timeout))


@pytest.mark.parametrize(
    ("cache_get_value", "expected"),
    [
        pytest.param(54321, 54321, id="cache_hit_positive"),
        pytest.param(None, None, id="cache_hit_negative"),
    ],
)
def test_get_cached_canvas_course_id_uses_cache_hit_without_course_lookup(
    monkeypatch, cache_get_value, expected
):
    """Test that a cache hit is returned without loading the course."""
    stub_cache = StubCache(get_value=cache_get_value)
    course_lookup_calls = []
    monkeypatch.setattr(utils, "cache", stub_cache)

    def _track_course_lookup(course_id):
        course_lookup_calls.append(course_id)

    monkeypatch.setattr(utils, "get_course_by_id", _track_course_lookup)

    assert utils.get_cached_canvas_course_id("course-v1:MITx+1+2026") == expected
    assert course_lookup_calls == []
    assert stub_cache.set_calls == []


@pytest.mark.parametrize(
    ("course", "expected_cached_value", "expected_result"),
    [
        pytest.param(
            SimpleNamespace(other_course_settings={"canvas_id": CANVAS_COURSE_ID_1}),
            CANVAS_COURSE_ID_1,
            CANVAS_COURSE_ID_1,
            id="cache_miss_with_canvas_id",
        ),
        pytest.param(
            SimpleNamespace(other_course_settings={}),
            None,
            None,
            id="cache_miss_without_canvas_id",
        ),
    ],
)
def test_get_cached_canvas_course_id_caches_result_on_miss(
    monkeypatch, course, expected_cached_value, expected_result
):
    """Test that a cache miss loads the course and caches the outcome.

    ``None`` is cached directly for courses without Canvas IDs.
    """
    stub_cache = StubCache()
    monkeypatch.setattr(utils, "cache", stub_cache)
    monkeypatch.setattr(
        utils, "settings", SimpleNamespace(CANVAS_COURSE_ID_CACHE_TIMEOUT=60)
    )
    monkeypatch.setattr(utils, "get_course_by_id", lambda _course_id: course)

    result = utils.get_cached_canvas_course_id("course-v1:MITx+1+2026")

    assert result == expected_result
    assert stub_cache.set_calls == [
        ("canvas_course_id:course-v1:MITx+1+2026", expected_cached_value, 60)
    ]


def test_get_cached_canvas_course_id_falls_back_to_lookup_when_cache_get_fails(
    monkeypatch, caplog
):
    """Test that a cache.get failure (e.g. cache backend outage) is treated as a miss.

    Logs a warning but still resolves and returns the Canvas course id via the
    course lookup, rather than treating the course as unlinked.
    """

    class RaisingGetCache(StubCache):
        """Cache stub whose get() simulates a cache backend outage."""

        def get(self, _key, _default=None):
            """Raise to simulate a cache backend outage."""
            msg = "cache backend unavailable"
            raise ConnectionError(msg)

    stub_cache = RaisingGetCache()
    monkeypatch.setattr(utils, "cache", stub_cache)
    monkeypatch.setattr(
        utils, "settings", SimpleNamespace(CANVAS_COURSE_ID_CACHE_TIMEOUT=60)
    )
    monkeypatch.setattr(
        utils,
        "get_course_by_id",
        lambda _course_id: SimpleNamespace(
            other_course_settings={"canvas_id": CANVAS_COURSE_ID_1}
        ),
    )

    with caplog.at_level(logging.WARNING):
        result = utils.get_cached_canvas_course_id("course-v1:MITx+1+2026")

    assert result == CANVAS_COURSE_ID_1
    assert "Could not read cached Canvas course id" in caplog.text


def test_get_cached_canvas_course_id_caches_none_when_course_not_found(
    monkeypatch, caplog
):
    """Test that a "course not found" lookup failure is cached as "not linked".

    Returns None and logs a warning. Unlike other lookup failures, this one is
    a genuine "not linked" outcome, so it's cached like any other negative
    result instead of being retried on every subsequent grade save.
    """
    stub_cache = StubCache()
    monkeypatch.setattr(utils, "cache", stub_cache)
    monkeypatch.setattr(
        utils, "settings", SimpleNamespace(CANVAS_COURSE_ID_CACHE_TIMEOUT=60)
    )

    def _raise(_course_id):
        msg = "course not found"
        raise Http404(msg)

    monkeypatch.setattr(utils, "get_course_by_id", _raise)

    with caplog.at_level(logging.WARNING):
        result = utils.get_cached_canvas_course_id("course-v1:MITx+1+2026")

    assert result is None
    assert stub_cache.set_calls == [
        ("canvas_course_id:course-v1:MITx+1+2026", None, 60)
    ]
    assert "Could not determine Canvas course id" in caplog.text


def test_get_cached_canvas_course_id_returns_none_and_skips_cache_on_unexpected_error(
    monkeypatch, caplog
):
    """Test that an unexpected lookup error (not "course not found") isn't cached.

    A transient failure (e.g. a modulestore timeout) should return None without
    caching it as "not linked", so the next grade save retries the lookup instead
    of treating the course as permanently unlinked.
    """
    stub_cache = StubCache()
    monkeypatch.setattr(utils, "cache", stub_cache)

    def _raise(_course_id):
        msg = "modulestore timeout"
        raise ConnectionError(msg)

    monkeypatch.setattr(utils, "get_course_by_id", _raise)

    with caplog.at_level(logging.ERROR):
        result = utils.get_cached_canvas_course_id("course-v1:MITx+1+2026")

    assert result is None
    assert stub_cache.set_calls == []
    assert "Unexpected error determining Canvas course id" in caplog.text


def test_get_cached_canvas_course_id_returns_id_when_cache_set_fails(
    monkeypatch, caplog
):
    """Test that a cache.set failure (e.g. cache backend outage) is handled.

    Logs a warning but still returns the resolved Canvas course id, so a cache
    outage can't cause a Canvas-linked course to be treated as unlinked.
    """

    class RaisingCache(StubCache):
        """Cache stub whose set() simulates a cache backend outage."""

        def set(self, _key, _value, _timeout=None):
            """Raise to simulate a cache backend outage."""
            msg = "cache backend unavailable"
            raise ConnectionError(msg)

    stub_cache = RaisingCache()
    monkeypatch.setattr(utils, "cache", stub_cache)
    monkeypatch.setattr(
        utils, "settings", SimpleNamespace(CANVAS_COURSE_ID_CACHE_TIMEOUT=60)
    )
    monkeypatch.setattr(
        utils,
        "get_course_by_id",
        lambda _course_id: SimpleNamespace(
            other_course_settings={"canvas_id": CANVAS_COURSE_ID_1}
        ),
    )

    with caplog.at_level(logging.WARNING):
        result = utils.get_cached_canvas_course_id("course-v1:MITx+1+2026")

    assert result == CANVAS_COURSE_ID_1
    assert "Could not cache Canvas course id" in caplog.text
