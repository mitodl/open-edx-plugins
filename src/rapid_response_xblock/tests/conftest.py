"""Pytest config"""
import json
import logging
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).parent.absolute()


def pytest_addoption(parser):
    """Pytest hook that adds command line options"""
    parser.addoption(
        "--disable-logging", action="store_true", default=False,
        help="Disable all logging during test run"
    )
    parser.addoption(
        "--error-log-only", action="store_true", default=False,
        help="Disable all logging output below 'error' level during test run"
    )


def pytest_configure(config):
    """Pytest hook that runs after command line options have been parsed"""
    if config.getoption("--disable-logging"):
        logging.disable(logging.CRITICAL)
    elif config.getoption("--error-log-only"):
        logging.disable(logging.WARNING)


@pytest.fixture()
def example_event(request):  # noqa: PT004
    """An example real event captured previously"""  # noqa: D401
    with Path.open(BASE_DIR / ".." / "test_data"/ "example_event.json") as f:
        request.cls.example_event = json.load(f)
        yield
