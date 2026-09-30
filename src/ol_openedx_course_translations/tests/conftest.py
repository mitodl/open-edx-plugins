"""Fixtures shared by every test module in this plugin."""

import pytest
from ol_openedx_course_translations.providers import llm_providers
from ol_openedx_course_translations.tasks import cached_benchmark


@pytest.fixture(autouse=True)
def _clear_temperature_cache():
    """
    Keep the negotiated-temperature cache from leaking between tests.

    It is process-global, so a test that records a rejection would otherwise
    decide what a later test's provider sends. Here rather than per module:
    a new test file that forgot to copy it would fail by ordering.
    """
    llm_providers._MODEL_TEMPERATURES.clear()  # noqa: SLF001
    yield
    llm_providers._MODEL_TEMPERATURES.clear()  # noqa: SLF001


@pytest.fixture(autouse=True)
def _clear_benchmark_cache():
    """
    Drop the block a worker would keep between tasks.

    A worker reuses it on purpose; a test must not, or one test's mocked
    modulestore answers the next one's read.
    """
    cached_benchmark.cache_clear()
    yield
    cached_benchmark.cache_clear()
