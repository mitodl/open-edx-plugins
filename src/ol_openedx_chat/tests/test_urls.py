"""Tests for ol_openedx_chat URL routing."""

import types

import pytest
from django.conf import settings
from django.urls import URLResolver, include, re_path
from django.urls.resolvers import RegexPattern, Resolver404


@pytest.fixture
def resolver():
    """Mount the plugin's urlpatterns the way PluginURLs mounts them."""
    from ol_openedx_chat.urls import urlpatterns  # noqa: PLC0415

    module = types.ModuleType("_ol_openedx_chat_test_urls")
    module.urlpatterns = [re_path(r"", include((urlpatterns, "ol_openedx_chat")))]
    import sys  # noqa: PLC0415

    sys.modules["_ol_openedx_chat_test_urls"] = module
    return URLResolver(RegexPattern(r"^/"), "_ol_openedx_chat_test_urls")


BASE = "/ol-openedx-chat/api/contact-us-enabled"


@pytest.mark.parametrize("path", [f"{BASE}/", BASE])
def test_course_less_route_resolves(resolver, path):
    """The Footer appends an empty string when there is no course."""
    match = resolver.resolve(path)
    assert match.url_name == "ol_contact_us_enabled"
    assert match.kwargs == {}


@pytest.mark.parametrize(
    "path",
    [
        f"{BASE}/course-v1:edX+DemoX+2024",
        f"{BASE}/course-v1:edX+DemoX+2024/",
    ],
)
def test_trailing_slash_resolves(resolver, path):
    """Both forms must work; the Footer builds this URL by concatenation."""
    match = resolver.resolve(path)
    assert match.url_name == "ol_contact_us_enabled_course"
    assert match.kwargs == {"course_key_string": "course-v1:edX+DemoX+2024"}


def test_malformed_but_routable_key_reaches_the_view(resolver):
    """X+Y+Z shape matches the regex so the view can return its 400."""
    match = resolver.resolve(f"{BASE}/a+b+c")
    assert match.kwargs == {"course_key_string": "a+b+c"}


@pytest.mark.parametrize(
    "path",
    [f"{BASE}/garbage", f"/evil{BASE}/", f"/evil{BASE}/course-v1:edX+DemoX+2024"],
)
def test_garbage_segment_does_not_resolve(resolver, path):
    """A non-key segment 404s at the regex, and the routes are not prefix-injectable."""
    with pytest.raises(Resolver404):
        resolver.resolve(path)


def test_course_key_pattern_is_used():
    """Guard against the pattern being hand-rolled instead of taken from settings."""
    from ol_openedx_chat.urls import urlpatterns  # noqa: PLC0415

    keyed = next(p for p in urlpatterns if p.name == "ol_contact_us_enabled_course")
    assert settings.COURSE_KEY_PATTERN in keyed.pattern._regex  # noqa: SLF001
