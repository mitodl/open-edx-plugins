"""Common test configuration"""

import pytest
import responses


@pytest.fixture()
def mocked_responses():
    """Mock requests responses"""
    with responses.RequestsMock() as rsps:
        yield rsps
