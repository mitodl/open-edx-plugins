"""
Tests for ol-openedx-course-sync utils.
"""

from unittest import mock

from ddt import data, ddt
from ol_openedx_course_sync.utils import copy_course_content
from openedx.core.djangolib.testing.utils import skip_unless_cms
from tests.utils import OLOpenedXCourseSyncTestCase
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.django import modulestore


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
