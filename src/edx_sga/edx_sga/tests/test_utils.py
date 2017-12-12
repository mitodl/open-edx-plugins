# -*- coding: utf-8 -*-
"""
Tests for SGA utility functions
"""
import pytest  # pylint: disable=import-error
from edx_sga.utils import is_finalized_submission


@pytest.mark.parametrize(
    'submission_data,expected_value', [
        ({'answer': {'finalized': True}}, True),
        ({'answer': {'filename': 'file.txt'}}, True),
        ({'answer': {}}, True),
        ({'answer': {'finalized': False}}, False),
        ({'answer': None}, False),
        ({}, False),
    ]
)
def test_is_finalized_submission(submission_data, expected_value):
    """Test for is_finalized_submission"""
    assert is_finalized_submission(submission_data) is expected_value
