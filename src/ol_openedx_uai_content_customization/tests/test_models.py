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


def test_duplicate_name_case_insensitive_rejected(db):  # noqa: ARG001
    """Two industries whose names differ only by case cannot both exist."""
    Industry.objects.create(name="Healthcare", short_code="HC")

    with pytest.raises(ValidationError):
        Industry(name="HEALTHCARE", short_code="HC2").full_clean()


def test_duplicate_short_code_case_insensitive_rejected(db):  # noqa: ARG001
    """Two industries whose short codes differ only by case cannot both exist."""
    Industry.objects.create(name="Healthcare", short_code="HC")

    with pytest.raises(ValidationError):
        Industry(name="Health", short_code="hc").full_clean()


def test_second_blank_short_code_rejected(db):  # noqa: ARG001
    """
    Only one industry may have a blank short_code.

    A blank short_code is the "Original" sentinel meaning no industry
    suffix; the short_code uniqueness constraint applies to it just like
    any other value, so a second blank row is rejected.
    """
    Industry.objects.create(name="Original", short_code="")

    with pytest.raises(ValidationError):
        Industry(name="Another Original", short_code="").full_clean()
