"""
Tests for ol-openedx-course-sync tasks.
"""

from unittest import mock

from ol_openedx_course_sync.tasks import async_course_sync
from openedx.core.djangolib.testing.utils import skip_unless_cms
from tests.utils import OLOpenedXCourseSyncTestCase
from xmodule.modulestore import ModuleStoreEnum


class TestTasks(OLOpenedXCourseSyncTestCase):
    """
    Test the ol_openedx_course_sync tasks.
    """

    @skip_unless_cms
    def test_async_course_sync(self):
        """
        Test the async_course_sync task.
        """
        with mock.patch(
            "ol_openedx_course_sync.tasks.copy_course_content"
        ) as mock_copy_course_content, mock.patch(
            "ol_openedx_course_sync.tasks.SignalHandler"
        ) as mock_signal_handler:
            mock_signal_handler.return_value = mock.Mock(
                course_published=mock.Mock(send=mock.Mock())
            )
            async_course_sync(
                str(self.source_course.usage_key.course_key),
                str(self.target_course.usage_key.course_key),
            )
            mock_copy_course_content.assert_has_calls(
                [
                    mock.call(
                        self.source_course.usage_key.course_key,
                        self.target_course.usage_key.course_key,
                        ModuleStoreEnum.BranchName.draft,
                    ),
                    mock.call(
                        self.source_course.usage_key.course_key,
                        self.target_course.usage_key.course_key,
                        ModuleStoreEnum.BranchName.published,
                    ),
                ]
            )
            mock_signal_handler.course_published.send.assert_called_once()
