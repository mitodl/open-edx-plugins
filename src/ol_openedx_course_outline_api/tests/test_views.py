"""Tests for the course outline API view's cache keying."""

from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from lms.djangoapps.course_api.blocks.api import get_blocks
from ol_openedx_course_outline_api.constants import (
    COURSE_OUTLINE_CACHE_SCHEMA_VERSION,
)
from ol_openedx_course_outline_api.views import (
    CourseOutlineView,
    get_collected_content_version,
)
from openedx.core.djangoapps.content.block_structure.api import update_course_in_cache
from openedx.core.djangoapps.content.block_structure.exceptions import (
    BlockStructureNotFound,
)
from openedx.core.djangoapps.content.block_structure.models import BlockStructureModel
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.django_utils import (
    TEST_DATA_SPLIT_MODULESTORE,
    ModuleStoreTestCase,
)
from xmodule.modulestore.tests.factories import BlockFactory, CourseFactory


def _fake_course():
    return SimpleNamespace(location="block-v1:org+num+run+type@course+block@course")


def _fake_structure(**overrides):
    # Derived from VERSION_FIELDS so the fake can't drift from what the platform
    # compares and leave the per-field test below vacuous.
    fields = dict.fromkeys(BlockStructureModel.VERSION_FIELDS, "BASE")
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _version_for(**overrides):
    with patch.object(BlockStructureModel, "get") as get_model:
        get_model.return_value = _fake_structure(**overrides)
        return get_collected_content_version(_fake_course())


def test_version_tracks_the_collected_structure():
    """Two different collected structures must not share a version string."""
    assert _version_for() == _version_for()
    assert _version_for() != _version_for(data_version="OTHER")


def test_version_tracks_every_field_the_platform_compares():
    """
    A recollection can change the response without touching course_version.

    BlockStructureStore.is_up_to_date compares all of VERSION_FIELDS, so keying on
    data_version alone would serve a stale outline after, say, a transformer
    version bump.
    """
    baseline = _version_for()
    for field_name in BlockStructureModel.VERSION_FIELDS:
        assert _version_for(**{field_name: "CHANGED"}) != baseline, (
            f"{field_name} does not affect the cache key"
        )


def test_no_version_when_structure_has_not_been_collected_yet():
    """
    Without a collected structure there is no version naming the content.

    get_blocks() builds one while serving the request, so anything cached here
    would be filed under a version that describes different content.
    """
    with patch.object(BlockStructureModel, "get") as get_model:
        get_model.side_effect = BlockStructureNotFound("some-key")
        assert get_collected_content_version(_fake_course()) is None


class CourseOutlineViewTests(ModuleStoreTestCase):
    """The response cache must track the block structure, not the modulestore."""

    MODULESTORE = TEST_DATA_SPLIT_MODULESTORE

    def setUp(self):
        super().setUp()
        cache.clear()
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()
        self.course = CourseFactory.create()
        chapter = BlockFactory.create(
            parent=self.course, category="chapter", display_name="Week 1"
        )
        BlockFactory.create(
            parent=chapter, category="sequential", display_name="Introduction"
        )

    def _call_view(self):
        request = APIRequestFactory().get("/")
        force_authenticate(request, user=self.user)
        return CourseOutlineView.as_view()(request, course_id=str(self.course.id))

    def _key_for(self, version, schema=COURSE_OUTLINE_CACHE_SCHEMA_VERSION):
        return (
            f"{settings.OL_COURSE_OUTLINE_API_CACHE_KEY_PREFIX}"
            f"s{schema}:{self.course.id}:{version}"
        )

    def _titles(self, response):
        return [module["title"] for module in response.data["modules"]]

    def test_section_hidden_from_learners_is_not_returned(self):
        """A section with 'Hide from Learners' checked must not reach the response."""
        BlockFactory.create(
            parent=self.course,
            category="chapter",
            display_name="Hidden Week",
            visible_to_staff_only=True,
        )

        response = self._call_view()

        assert response.status_code == status.HTTP_200_OK
        assert "Week 1" in self._titles(response)
        assert "Hidden Week" not in self._titles(response)

    def test_first_request_without_a_collected_structure_is_not_cached(self):
        """
        get_blocks() collects the structure while serving the first request.

        Nothing may be cached under a guessed version, but the request that
        follows it must find the newly collected structure and cache normally.
        """
        with patch(
            "ol_openedx_course_outline_api.views.cache", wraps=cache
        ) as cache_spy:
            first = self._call_view()

        assert first.status_code == status.HTTP_200_OK
        cache_spy.set.assert_not_called()
        assert get_collected_content_version(self.course) is not None

        with patch(
            "ol_openedx_course_outline_api.views.get_blocks", wraps=get_blocks
        ) as spy:
            self._call_view()
            self._call_view()

        assert spy.call_count == 1, "the second request should have populated the cache"

    def test_stale_structure_is_not_recached_under_the_new_course_version(self):
        # Collect the structure first; the very first request predates it and is
        # deliberately not cached.
        self._call_view()
        first = self._call_view()
        assert first.status_code == status.HTTP_200_OK

        # Rotate course_version while the collected structure stays put: course is
        # a direct-only category so update_item publishes, but ModuleStoreTestCase
        # disables signals, so the rebuild that would follow never runs.
        store = modulestore()
        course = store.get_course(self.course.id)
        course.display_name = "Renamed after the outline was cached"
        store.update_item(course, self.user.id)
        new_course_version = str(store.get_course(self.course.id).course_version)

        with patch(
            "ol_openedx_course_outline_api.views.get_blocks", wraps=get_blocks
        ) as spy:
            second = self._call_view()

        assert second.status_code == status.HTTP_200_OK
        assert spy.call_count == 0, "served a rebuilt outline instead of the cached one"
        assert second.data == first.data
        assert cache.get(self._key_for(new_course_version)) is None

    def test_outline_rendered_during_the_rebuild_window_is_not_pinned(self):
        """
        The reported bug, end to end: hide a section in Studio, it keeps showing.

        Hiding a section advances course_version immediately, but the collected
        block structure is rebuilt asynchronously. A request arriving in between
        renders the section as still visible. Keyed on course_version that body
        was filed under the post-rebuild key and outlived the rebuild.
        """
        self._call_view()  # collect the structure
        assert "Week 1" in self._titles(self._call_view())

        store = modulestore()
        chapter = store.get_item(self.course.id.make_usage_key("chapter", "Week_1"))
        chapter.visible_to_staff_only = True
        store.update_item(chapter, self.user.id)

        # Inside the window the structure is still the pre-hide one, so the
        # section legitimately still renders.
        assert "Week 1" in self._titles(self._call_view())

        update_course_in_cache(self.course.id)  # the rebuild lands

        response = self._call_view()

        assert response.status_code == status.HTTP_200_OK
        assert "Week 1" not in self._titles(response), (
            "served an outline rendered before the structure was rebuilt"
        )

    def test_entry_cached_under_another_schema_version_is_not_served(self):
        self._call_view()  # collect the structure so a version exists
        version = get_collected_content_version(
            modulestore().get_course(self.course.id)
        )
        sentinel = {"course_id": "SENTINEL", "generated_at": "SENTINEL", "modules": []}
        for schema in (
            COURSE_OUTLINE_CACHE_SCHEMA_VERSION - 1,
            COURSE_OUTLINE_CACHE_SCHEMA_VERSION + 1,
        ):
            cache.set(self._key_for(version, schema=schema), sentinel, 300)

        response = self._call_view()

        assert response.status_code == status.HTTP_200_OK
        assert response.data["course_id"] != "SENTINEL"
        assert cache.get(self._key_for(version)) is not None
