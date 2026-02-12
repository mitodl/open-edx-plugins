"""
Tests for ol-openedx-course-sync utils.
"""

from unittest import mock

import pytest
from common.djangoapps.student.tests.factories import UserFactory
from ddt import data, ddt, unpack
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from ol_openedx_course_sync.constants import STATIC_TAB_TYPE
from ol_openedx_course_sync.models import (
    CourseSyncMapping,
    CourseSyncOrganization,
)
from ol_openedx_course_sync.utils import (
    copy_course_content,
    copy_static_tabs,
    get_course_sync_service_user,
    get_syncable_course_mappings,
    sync_discussions_configuration,
    update_default_tabs,
    sync_course_handouts,
    sync_course_updates,
)
from openedx.core.djangoapps.content.course_overviews.tests.factories import (
    CourseOverviewFactory,
)
from openedx.core.djangoapps.discussions.models import DiscussionsConfiguration
from openedx.core.djangolib.testing.utils import skip_unless_cms
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.factories import BlockFactory
from xmodule.tabs import StaticTab

from tests.utils import OLOpenedXCourseSyncTestCase


@ddt
class TestUtils(OLOpenedXCourseSyncTestCase):
    """
    Test the ol_openedx_course_sync utils.
    """

    @skip_unless_cms
    @data(ModuleStoreEnum.BranchName.draft, ModuleStoreEnum.BranchName.published)
    def test_copy_course_content(self, branch):
        """
        Test the copy_course_content function.
        """
        with mock.patch(
            "ol_openedx_course_sync.utils.modulestore"
        ) as mixed_modulestore_mock:
            split_modulestore_mock = mock.Mock()
            split_modulestore_mock.copy = mock.Mock()
            mixed_modulestore_mock.return_value = mock.Mock(
                make_course_usage_key=mock.Mock(
                    return_value=modulestore().make_course_usage_key(
                        self.source_course.usage_key.course_key
                    )
                ),
                _get_modulestore_for_courselike=mock.Mock(
                    side_effect=[split_modulestore_mock, split_modulestore_mock]
                ),
            )
            copy_course_content(
                self.source_course.usage_key.course_key,
                self.target_course.usage_key.course_key,
                branch,
            )
            split_modulestore_mock.copy.assert_called_once()

    def test_copy_static_tabs(self):
        """
        Test the copy_static_tabs function.
        """
        self.test_tab = BlockFactory.create(
            parent_location=self.source_course.location,
            category="static_tab",
            display_name="Static_1",
        )
        tab_usage_key = self.source_course.id.make_usage_key(
            STATIC_TAB_TYPE, self.test_tab.usage_key.block_id
        )
        self.source_course.tabs.append(
            StaticTab(name=self.test_tab.name, url_slug=tab_usage_key.block_id)
        )
        self.store.update_item(
            self.source_course,
            None,
        )
        copy_static_tabs(
            self.source_course.usage_key.course_key,
            self.target_course.usage_key.course_key,
            self.user,
        )
        # refresh target course to get updated tabs
        target_course = self.store.get_course(self.target_course.usage_key.course_key)
        assert len(self.source_course.tabs) == len(target_course.tabs)

    def test_copy_default_tabs(self):
        """
        Test the copy_default_tabs function.
        """
        for tab in self.source_course.tabs:
            if tab.type != "progress":
                continue
            tab.is_hidden = True
        self.store.update_item(self.source_course, None)

        update_default_tabs(
            self.source_course.usage_key.course_key,
            self.target_course.usage_key.course_key,
            self.user,
        )

        # refresh target course to get updated tabs
        target_course = self.store.get_course(self.target_course.usage_key.course_key)
        for tab in target_course.tabs:
            if tab.type != "progress":
                continue
            assert tab.is_hidden is True

    def test_sync_course_updates(self):
        pass

    def test_sync_course_handouts(self):
        pass

    @data(
        [
            # Test: updates fields
            {
                "enabled": True,
                "posting_restrictions": "disabled",
                "lti_configuration": None,
                "enable_in_context": True,
                "enable_graded_units": True,
                "unit_level_visibility": True,
                "plugin_configuration": {"plugin": "value"},
                "provider_type": "test_provider",
            },
            {
                "enabled": False,
                "posting_restrictions": "enabled",
                "lti_configuration": None,
                "enable_in_context": False,
                "enable_graded_units": False,
                "unit_level_visibility": False,
                "plugin_configuration": {},
                "provider_type": "old_provider",
            },
            {
                "enabled": True,
                "posting_restrictions": "disabled",
                "lti_configuration": None,
                "enable_in_context": True,
                "enable_graded_units": True,
                "unit_level_visibility": True,
                "plugin_configuration": {"plugin": "value"},
                "provider_type": "test_provider",
            },
        ],
        [
            # Test: no changes
            {
                "enabled": True,
                "posting_restrictions": "disabled",
                "lti_configuration": None,
                "enable_in_context": True,
                "enable_graded_units": True,
                "unit_level_visibility": True,
                "plugin_configuration": {"plugin": "value"},
                "provider_type": "test_provider",
            },
            {
                "enabled": True,
                "posting_restrictions": "disabled",
                "lti_configuration": None,
                "enable_in_context": True,
                "enable_graded_units": True,
                "unit_level_visibility": True,
                "plugin_configuration": {"plugin": "value"},
                "provider_type": "test_provider",
            },
            {
                "enabled": True,
                "posting_restrictions": "disabled",
                "lti_configuration": None,
                "enable_in_context": True,
                "enable_graded_units": True,
                "unit_level_visibility": True,
                "plugin_configuration": {"plugin": "value"},
                "provider_type": "test_provider",
            },
        ],
    )
    @unpack
    @skip_unless_cms
    @override_settings(OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME="service_worker")
    def test_sync_discussions_configuration(
        self, source_fields, target_fields, expected_fields
    ):
        """
        Test the sync_discussions_configuration function with parametrized inputs.
        """
        user = UserFactory.create(username="service_worker")
        source_key = self.source_course.usage_key.course_key
        target_key = self.target_course.usage_key.course_key

        DiscussionsConfiguration.objects.create(context_key=source_key, **source_fields)
        target_config = DiscussionsConfiguration.objects.create(
            context_key=target_key, **target_fields
        )

        sync_discussions_configuration(source_key, target_key, user)
        target_config.refresh_from_db()

        for field, expected_value in expected_fields.items():
            assert getattr(target_config, field) == expected_value

    @data(
        [
            False,
            False,
            False,
            False,
            False,
            False,
            None,
        ],
        [
            False,
            True,
            False,
            False,
            False,
            False,
            None,
        ],
        [
            True,
            True,
            False,
            False,
            False,
            True,
            None,
        ],
        [
            True,
            True,
            True,
            False,
            False,
            False,
            None,
        ],
        [
            True,
            True,
            True,
            True,
            False,
            False,
            None,
        ],
        [
            True,
            True,
            True,
            True,
            True,
            False,
            1,
        ],
    )
    @unpack
    @skip_unless_cms
    def test_get_syncable_course_mappings(  # noqa: PLR0913
        self,
        course_sync_org_exists,
        course_sync_org_active,
        service_user_exists,
        mapping_exists,
        mapping_active,
        raise_exception,
        expected_sync_mappings_count,
    ):
        """
        Test the get_syncable_course_mappings function.
        """
        source_key = self.source_course.usage_key.course_key
        target_key = self.target_course.usage_key.course_key

        CourseOverviewFactory.create(id=source_key)
        CourseOverviewFactory.create(id=target_key)

        if course_sync_org_exists:
            CourseSyncOrganization.objects.create(
                organization=source_key.org, is_active=course_sync_org_active
            )

        if service_user_exists:
            UserFactory.create(username="service_worker")

        if mapping_exists:
            CourseSyncMapping.objects.create(
                source_course=source_key,
                target_course=target_key,
                is_active=mapping_active,
            )

        if raise_exception:
            with pytest.raises(ImproperlyConfigured):
                get_syncable_course_mappings(source_key)
        else:
            with override_settings(
                OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME="service_worker"
            ):
                actual_sync_mappings = get_syncable_course_mappings(source_key)
            if expected_sync_mappings_count is None:
                assert actual_sync_mappings is None
            else:
                assert actual_sync_mappings.count() == expected_sync_mappings_count


@pytest.mark.django_db
@skip_unless_cms
@pytest.mark.parametrize(
    "cache_hit",
    [True, False],
)
def test_get_course_sync_service_user_cache(settings, cache_hit):
    """
    Test get_course_sync_service_user function for cache hit and miss.
    """
    settings.OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME = "service_worker"
    mock_user = mock.Mock()
    with (
        mock.patch(
            "ol_openedx_course_sync.utils.get_cache_key", return_value="cache_key"
        ),
        mock.patch(
            "ol_openedx_course_sync.utils.TieredCache.get_cached_response"
        ) as mock_get_cached_response,
        mock.patch("ol_openedx_course_sync.utils.User.objects.filter") as mock_filter,
        mock.patch(
            "ol_openedx_course_sync.utils.TieredCache.set_all_tiers"
        ) as mock_set_all_tiers,
    ):
        mock_get_cached_response.return_value.is_found = cache_hit
        mock_get_cached_response.return_value.value = mock_user
        mock_filter.return_value.first.return_value = mock_user
        user = get_course_sync_service_user()
        if cache_hit:
            assert user == mock_user
            mock_set_all_tiers.assert_not_called()
        else:
            mock_set_all_tiers.assert_called_once_with("cache_key", mock_user)
            assert user == mock_user
