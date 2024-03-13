"""Pytest config"""
import json
import logging
import os

import pytest


BASE_DIR = os.path.dirname(os.path.realpath(__file__))


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


@pytest.fixture(scope="function")
def example_event(request):
    """An example real event captured previously"""
    with open(os.path.join(BASE_DIR, "..", "test_data", "example_event.json")) as f:
        request.cls.example_event = json.load(f)
        yield
