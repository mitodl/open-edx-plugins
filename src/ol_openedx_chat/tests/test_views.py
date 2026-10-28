"""Tests for the ContactUsEnabledView API view."""

import pytest
from edx_django_utils.cache import RequestCache
from edx_toggles.toggles.testutils import override_waffle_flag
from ol_openedx_chat.compat import get_contact_us_enabled_flag
from ol_openedx_chat.views import ContactUsEnabledView
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.waffle_utils.models import (
    WaffleFlagCourseOverrideModel,
    WaffleFlagOrgOverrideModel,
)
from rest_framework import status
from rest_framework.permissions import AllowAny

COURSE_KEY_STRING = "course-v1:edX+DemoX+2024"
OTHER_COURSE_KEY_STRING = "course-v1:edX+OtherX+2024"


def _get(request_factory, course_key_string=None):
    """Call the view the way the URLconf will."""
    request = request_factory.get("/")
    return ContactUsEnabledView().get(request, course_key_string=course_key_string)


def test_view_declares_no_auth_and_no_throttle():
    """A 401 or a 429 both read as 'off' to a fail-closed client."""
    assert ContactUsEnabledView.permission_classes == [AllowAny]
    assert ContactUsEnabledView.authentication_classes == []
    assert ContactUsEnabledView.throttle_classes == []


@pytest.mark.django_db
def test_no_flag_row_returns_false(request_factory):
    """The state every environment is in before the flag is provisioned."""
    assert _get(request_factory).data == {"enabled": False}


@pytest.mark.django_db
@pytest.mark.parametrize("flag_value", [True, False])
def test_global_flag_value_is_returned(request_factory, flag_value):
    """Site-wide on/off, with no course key supplied."""
    with override_waffle_flag(get_contact_us_enabled_flag(), active=flag_value):
        assert _get(request_factory).data == {"enabled": flag_value}


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("global_value", "override_choice", "expected_for_course", "expected_for_other"),
    [
        (True, WaffleFlagCourseOverrideModel.ALL_CHOICES.off, False, True),
        (False, WaffleFlagCourseOverrideModel.ALL_CHOICES.on, True, False),
    ],
)
def test_course_override_beats_global(
    request_factory,
    global_value,
    override_choice,
    expected_for_course,
    expected_for_other,
):
    """Per-course exception in both directions, leaving other courses alone."""
    flag = get_contact_us_enabled_flag()
    WaffleFlagCourseOverrideModel.objects.create(
        waffle_flag=flag.name,
        course_id=CourseKey.from_string(COURSE_KEY_STRING),
        override_choice=override_choice,
        enabled=True,
    )
    with override_waffle_flag(flag, active=global_value):
        RequestCache.clear_all_namespaces()
        assert _get(request_factory, COURSE_KEY_STRING).data == {
            "enabled": expected_for_course
        }
        RequestCache.clear_all_namespaces()
        assert _get(request_factory, OTHER_COURSE_KEY_STRING).data == {
            "enabled": expected_for_other
        }


@pytest.mark.django_db
def test_course_beats_org_beats_global(request_factory):
    """The README promises this precedence; both rungs have to hold.

    `CourseWaffleFlag._get_course_override_value` reads the course row, then the
    org row, then falls through to the plain flag, so an org-wide force-on has
    to lose to a per-course force-off.
    """
    flag = get_contact_us_enabled_flag()
    WaffleFlagOrgOverrideModel.objects.create(
        waffle_flag=flag.name,
        org="edX",
        override_choice=WaffleFlagOrgOverrideModel.ALL_CHOICES.on,
        enabled=True,
    )
    with override_waffle_flag(flag, active=False):
        RequestCache.clear_all_namespaces()
        # Org beats global.
        assert _get(request_factory, COURSE_KEY_STRING).data == {"enabled": True}

    WaffleFlagCourseOverrideModel.objects.create(
        waffle_flag=flag.name,
        course_id=CourseKey.from_string(COURSE_KEY_STRING),
        override_choice=WaffleFlagCourseOverrideModel.ALL_CHOICES.off,
        enabled=True,
    )
    with override_waffle_flag(flag, active=False):
        RequestCache.clear_all_namespaces()
        # Course beats org.
        assert _get(request_factory, COURSE_KEY_STRING).data == {"enabled": False}
        RequestCache.clear_all_namespaces()
        # Sibling course in the same org still gets the org force-on.
        assert _get(request_factory, OTHER_COURSE_KEY_STRING).data == {"enabled": True}


@pytest.mark.django_db
def test_disabled_override_row_falls_back_to_global(request_factory):
    """Overrides are append-only; an exception is removed by adding enabled=False."""
    flag = get_contact_us_enabled_flag()
    course_key = CourseKey.from_string(COURSE_KEY_STRING)
    WaffleFlagCourseOverrideModel.objects.create(
        waffle_flag=flag.name,
        course_id=course_key,
        override_choice=WaffleFlagCourseOverrideModel.ALL_CHOICES.off,
        enabled=False,
    )
    with override_waffle_flag(flag, active=True):
        RequestCache.clear_all_namespaces()
        assert _get(request_factory, COURSE_KEY_STRING).data == {"enabled": True}


@pytest.mark.django_db
def test_unknown_course_falls_back_to_global(request_factory):
    """A well-formed key for a course that does not exist is not an error."""
    with override_waffle_flag(get_contact_us_enabled_flag(), active=True):
        response = _get(request_factory, "course-v1:No+Such+Course")
    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"enabled": True}


@pytest.mark.django_db
def test_invalid_course_key_returns_400(request_factory):
    """Only X+Y+Z-shaped input reaches the view; it must 400, not 500."""
    response = _get(request_factory, "a+b+c")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == {"error": "Invalid course_key."}


@pytest.mark.django_db
def test_anonymous_request_succeeds(request_factory):
    """Most page loads that need the launcher have no session at all."""
    request = request_factory.get("/")
    response = ContactUsEnabledView.as_view()(request)
    response.render()
    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"enabled": False}


@pytest.mark.django_db
def test_response_is_browser_cacheable(request_factory):
    """max-age bounds how long a learner keeps a stale answer after a flag flip."""
    response = ContactUsEnabledView.as_view()(request_factory.get("/"))
    response.render()
    assert "max-age=60" in response["Cache-Control"]
    assert "public" in response["Cache-Control"]
