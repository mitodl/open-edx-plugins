"""Tests for the util methods"""

from unittest.mock import MagicMock, patch

from ddt import data, ddt, unpack
from ol_openedx_chat.utils import (
    get_checkpoint_and_thread_id,
    get_course,
    get_transcript_asset_id,
    is_aside_applicable_to_block,
    is_ol_chat_enabled_for_course,
)
from opaque_keys.edx.locator import BlockUsageLocator, CourseLocator
from xmodule.modulestore.tests.factories import BlockFactory

from tests.utils import OLChatTestCase


@ddt
class OLChatUtilTests(OLChatTestCase):
    @data(
        *[
            ("problem", True, True, True, True),
            ("problem", True, True, True, False),
            ("problem", True, False, False, False),
            ("problem", False, True, True, False),
            ("problem", False, False, False, False),
            ("video", True, True, True, True),
            ("video", True, True, True, False),
            ("video", True, False, True, False),
            ("video", False, True, False, False),
            ("video", False, False, False, False),
        ]
    )
    @unpack
    def test_is_ol_chat_enabled_for_course(
        self,
        block_category,
        video_block_setting,
        problem_block_setting,
        expected_is_enabled,
        is_course_key_deprecated,
    ):
        """
        Test the is_ol_chat_enabled_for_course function
        """
        with patch("ol_openedx_chat.utils.get_course_by_id") as mock_get_course_by_id:
            self.course.other_course_settings = {
                "OL_OPENEDX_CHAT_VIDEO_BLOCK_ENABLED": video_block_setting,
                "OL_OPENEDX_CHAT_PROBLEM_BLOCK_ENABLED": problem_block_setting,
            }
            mock_get_course_by_id.return_value = self.course
            block = (
                self.problem_block if block_category == "problem" else self.video_block
            )
            if is_course_key_deprecated:
                course_key = CourseLocator(
                    block.usage_key.course_key.org,
                    block.usage_key.course_key.course,
                    block.usage_key.course_key.run,
                    deprecated=True,
                )
                usage_key = BlockUsageLocator(
                    course_key=course_key,
                    block_type=block_category,
                    block_id=block_category,
                )
                block = BlockFactory.create(
                    category=block_category,
                    parent_location=self.vertical.location,
                    display_name=f"A {block_category} Block",
                    user_id=self.user.id,
                    location=usage_key,
                )
                assert is_ol_chat_enabled_for_course(block) == expected_is_enabled
            else:
                assert is_ol_chat_enabled_for_course(block) == expected_is_enabled

    @data("problem", "video")
    def test_is_ol_chat_enabled_for_course_when_no_course_found(self, block_category):
        """
        Tests that `is_ol_chat_enabled_for_course` return
        True when `get_course_by_id` fails
        """
        with patch("ol_openedx_chat.utils.get_course_by_id") as mock_get_course_by_id:
            mock_get_course_by_id.side_effect = Exception()
            block = (
                self.problem_block if block_category == "problem" else self.video_block
            )
            assert is_ol_chat_enabled_for_course(block)

    @data(
        *[
            ("problem", True),
            ("video", True),
            ("html", False),
        ]
    )
    @unpack
    def test_is_aside_applicable_to_block(self, block_category, is_aside_applicable):
        """Tests that `is_aside_applicable_to_block` returns the expected value"""
        if block_category == "problem":
            block = self.problem_block
        elif block_category == "video":
            block = self.video_block
        elif block_category == "html":
            block = self.html_block
        assert is_aside_applicable_to_block(block) == is_aside_applicable

    @data(
        (None, None, None),
        ("Hello! How can I help you?\n\nNo JSON here\n\n", None, None),
        (
            (
                "Hello! How can I help you?\n\n"
                '<!-- {"checkpoint_pk": 123, "thread_id": "abc123"} -->\n\n'
            ),
            "abc123",
            "123",
        ),
        (
            (
                b"Hello! How can I help you?\n\n"
                b'<!-- {"checkpoint_pk": 456, "thread_id": "xyz789"} -->\n\n'
            ),
            "xyz789",
            "456",
        ),
        ("Some text <!-- {invalid json} -->", None, None),
        ('<!-- {"foo": "bar"} -->', None, "None"),
    )
    @unpack
    def test_get_checkpoint_and_thread_id(
        self, content, expected_thread_id, expected_checkpoint_pk
    ):
        """Tests that `get_checkpoint_and_thread_id` extracts the correct values"""
        thread_id, checkpoint_pk = get_checkpoint_and_thread_id(content)
        assert thread_id == expected_thread_id
        assert checkpoint_pk == expected_checkpoint_pk

    @data(
        (False, True),  # Normal course key
        (True, True),  # Deprecated course key
    )
    @unpack
    def test_get_course_success(self, is_deprecated, expected_course_found):
        """Test that get_course returns the course successfully"""
        with patch("ol_openedx_chat.utils.get_course_by_id") as mock_get_course_by_id:
            mock_get_course_by_id.return_value = self.course

            if is_deprecated:
                course_key = CourseLocator(
                    self.course.id.org,
                    self.course.id.course,
                    self.course.id.run,
                    deprecated=True,
                )
                usage_key = BlockUsageLocator(
                    course_key=course_key,
                    block_type="problem",
                    block_id="test_block",
                )
                block = BlockFactory.create(
                    category="problem",
                    parent_location=self.vertical.location,
                    display_name="Test Block",
                    user_id=self.user.id,
                    location=usage_key,
                )
            else:
                block = self.problem_block

            course = get_course(block)
            assert course == self.course if expected_course_found else course is None

    def test_get_course_exception(self):
        """Test that get_course returns None when an exception occurs"""
        with patch("ol_openedx_chat.utils.get_course_by_id") as mock_get_course_by_id:
            mock_get_course_by_id.side_effect = Exception("Course not found")
            course = get_course(self.problem_block)
            assert course is None

    @data(
        # (course_language, transcripts, edx_video_id_transcripts, expected_asset_id_suffix)  # noqa: ERA001,E501
        (
            "en",
            {"en": "transcript-en.srt", "es": "transcript-es.srt"},
            [],
            "transcript-en.srt",
        ),  # Course language transcript
        (
            "es",
            {"en": "transcript-en.srt", "es": "transcript-es.srt"},
            [],
            "transcript-es.srt",
        ),  # Non-English course language
        (
            "es_419",
            {
                "en": "transcript-en.srt",
                "es": "transcript-es.srt",
                "es-419": "transcript-es-419.srt",
            },
            [],
            "transcript-es-419.srt",
        ),  # Non-English course language
        (
            "de_DE",
            {
                "en": "transcript-en.srt",
                "es": "transcript-es.srt",
                "de-DE": "transcript-de-DE.srt",
            },
            [],
            "transcript-de-DE.srt",
        ),  # Non-English course language
        ("es", {}, ["es"], "video-id-es.srt"),  # Transcript from edx_video_id
        (
            "es_419",
            {},
            ["es-419"],
            "video-id-es-419.srt",
        ),  # Transcript from edx_video_id
        ("de_DE", {}, ["de-DE"], "video-id-de-DE.srt"),  # Transcript from edx_video_id
        (
            "es",
            {"en": "transcript-en.srt"},
            [],
            "transcript-en.srt",
        ),  # Fallback to English transcript
        ("es", {}, ["en"], "video-id-en.srt"),  # Fallback to English from edx_video_id
        ("es", {}, [], None),  # No transcript available
    )
    @unpack
    def test_get_transcript_asset_id(
        self,
        course_language,
        transcripts,
        edx_video_id_transcripts,
        expected_asset_id_suffix,
    ):
        """Test that get_transcript_asset_id returns the correct asset ID"""
        with (
            patch("ol_openedx_chat.utils.get_course_by_id") as mock_get_course_by_id,
            patch(
                "ol_openedx_chat.utils.get_available_transcript_languages"
            ) as mock_get_transcripts,
            patch(
                "ol_openedx_chat.utils.Transcript.asset_location"
            ) as mock_asset_location,
        ):
            # Setup course language
            self.course.language = course_language
            mock_get_course_by_id.return_value = self.course

            # Setup video block
            self.video_block.edx_video_id = "video-id"
            mock_transcripts_info = {"transcripts": transcripts}
            self.video_block.get_transcripts_info = MagicMock(
                return_value=mock_transcripts_info
            )

            # Setup edx_video_id transcripts
            mock_get_transcripts.return_value = edx_video_id_transcripts

            # Setup mock return value
            if expected_asset_id_suffix:
                mock_asset_location.return_value = (
                    f"asset-id-{expected_asset_id_suffix}"
                )

            result = get_transcript_asset_id(self.video_block)

            if expected_asset_id_suffix:
                assert result == f"asset-id-{expected_asset_id_suffix}"
                mock_asset_location.assert_called_once()
            else:
                assert result is None

    def test_get_transcript_asset_id_exception(self):
        """Test that get_transcript_asset_id returns None when an exception occurs"""
        with patch("ol_openedx_chat.utils.get_course_by_id") as mock_get_course_by_id:
            mock_get_course_by_id.return_value = self.course
            self.video_block.get_transcripts_info = MagicMock(
                side_effect=Exception("Transcript error")
            )

            result = get_transcript_asset_id(self.video_block)
            assert result is None
