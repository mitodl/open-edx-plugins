"""Tests for the Industry model."""

import pytest
from django.core.exceptions import ValidationError
from ol_openedx_uai_content_customization.models import Industry


@pytest.mark.parametrize(
    "short_code",
    ["HC", "hc-2", "HC.2", "HC_2", "HC~2", "HC:2", ""],
)
def test_valid_short_codes_pass_full_clean(db, short_code):  # noqa: ARG001
    """Characters allowed in a course key segment pass validation."""
    industry = Industry(name="Healthcare", short_code=short_code)
    industry.full_clean()


@pytest.mark.parametrize(
    "short_code",
    ["HC 2", "HC+2", "HC/2", "HC@2", "HC#2"],
)
def test_invalid_short_codes_raise_on_full_clean(db, short_code):  # noqa: ARG001
    """
    Characters CourseKey.from_string() would reject are rejected up front.

    short_code is spliced directly into the generated course key's number
    segment, so a value with a space, "+", or other disallowed character
    would otherwise save successfully in admin and only fail later, deep
    into course generation.
    """
    industry = Industry(name="Healthcare", short_code=short_code)
    with pytest.raises(ValidationError, match="short_code"):
        industry.full_clean()
