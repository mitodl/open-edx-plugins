"""
Tests for ol-openedx-course-sync utils.
"""

from unittest import mock

from ddt import data, ddt
from openedx.core.djangolib.testing.utils import skip_unless_cms
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.factories import BlockFactory
from xmodule.tabs import StaticTab

from ol_openedx_course_sync.constants import STATIC_TAB_TYPE
from ol_openedx_course_sync.utils import (
    copy_course_content,
    copy_static_tabs,
    update_default_tabs,
)
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
