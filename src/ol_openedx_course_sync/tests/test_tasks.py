"""
Tests for ol-openedx-course-sync tasks.
"""

from unittest import mock

from common.djangoapps.student.tests.factories import UserFactory
from django.test import override_settings
from openedx.core.djangolib.testing.utils import skip_unless_cms
from tests.utils import OLOpenedXCourseSyncTestCase
from xmodule.modulestore import ModuleStoreEnum

from ol_openedx_course_sync.tasks import async_course_sync


@override_settings(OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME="service_worker")
class TestReSyncTasks(OLOpenedXCourseSyncTestCase):
    """
    Test the ol_openedx_course_sync tasks.
    """

    @skip_unless_cms
    def test_async_course_sync(self):
        """
        Test the async_course_sync task works as expected.
        """
        user = UserFactory.create(username="service_worker")
        with mock.patch(
            "ol_openedx_course_sync.tasks.copy_course_content"
        ) as mock_copy_course_content, mock.patch(
            "ol_openedx_course_sync.tasks.SignalHandler"
        ) as mock_signal_handler, mock.patch(
            "ol_openedx_course_sync.tasks.modulestore"
        ) as mock_modulestore, mock.patch(
            "ol_openedx_course_sync.tasks.copy_course_videos"
        ) as mock_copy_course_videos:
            mock_copy_all_course_assets = mock.Mock()
            mock_delete_all_course_assets = mock.Mock()
            mock_contentstore = mock.Mock()
            mock_contentstore.copy_all_course_assets = mock_copy_all_course_assets
            mock_contentstore.delete_all_course_assets = mock_delete_all_course_assets

            mock_module_store_instance = mock.Mock()
            mock_module_store_instance.contentstore = mock_contentstore
            mock_modulestore.return_value = mock_module_store_instance
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
                        user.id,
                    ),
                    mock.call(
                        self.source_course.usage_key.course_key,
                        self.target_course.usage_key.course_key,
                        ModuleStoreEnum.BranchName.published,
                        user.id,
                    ),
                ]
            )
            mock_signal_handler.course_published.send.assert_called_once()
            mock_copy_course_videos.assert_called_once_with(
                self.source_course.usage_key.course_key,
                self.target_course.usage_key.course_key,
            )
            mock_copy_all_course_assets.assert_called_once()
            mock_delete_all_course_assets.assert_called_once()
