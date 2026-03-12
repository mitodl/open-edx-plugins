"""Pytest config"""

import logging

from tests.fixtures import mock_anonymous_user, mock_user, rf  # noqa: F401


def pytest_addoption(parser):
    """Pytest hook that adds command line options"""
    parser.addoption(
        "--disable-logging",
        action="store_true",
        default=False,
        help="Disable all logging during test run",
    )
    parser.addoption(
        "--error-log-only",
        action="store_true",
        default=False,
        help="Disable all logging output below 'error' level during test run",
    )


def pytest_configure(config):
    """Pytest hook that runs after command line options have been parsed"""
    if config.getoption("--disable-logging"):
        logging.disable(logging.CRITICAL)
    elif config.getoption("--error-log-only"):
        logging.disable(logging.WARNING)
