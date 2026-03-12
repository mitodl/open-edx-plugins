"""Tests for AddDestLangForVideoBlock filter pipeline step."""

import pytest
from ol_openedx_auto_select_language.constants import (
    ENGLISH_LANGUAGE_CODE,
)
from ol_openedx_auto_select_language.filters import (
    AddDestLangForVideoBlock,
)

MODULE = "ol_openedx_auto_select_language.filters"


def _make_step(mocker):
    """Create an AddDestLangForVideoBlock step with mock args."""
    return AddDestLangForVideoBlock(
        filter_type=mocker.Mock(),
        running_pipeline=mocker.Mock(),
    )


class TestAddDestLangForVideoBlock:
    """Tests for the AddDestLangForVideoBlock pipeline step."""

    @pytest.mark.parametrize(
        ("course_lang", "transcripts", "expected_lang"),
        [
            (
                "es",
                {"es": "spanish.srt", "en": "english.srt"},
                "es",
            ),
            (
                "zh_HANS",
                {"zh-Hans": "chinese.srt", "en": "english.srt"},
                "zh-Hans",
            ),
            (
                "fr",
                {"en": "english.srt"},
                ENGLISH_LANGUAGE_CODE,
            ),
        ],
    )
    def test_video_block_dest_lang(
        self,
        mocker,
        course_lang,
        transcripts,
        expected_lang,
    ):
        """Test dest_lang set for video block based on transcripts."""
        mock_ms = mocker.patch(f"{MODULE}.modulestore")
        mock_video = mocker.Mock()
        mock_video.get_transcripts_info.return_value = {"transcripts": transcripts}
        mock_ms.return_value.get_item.return_value = mock_video

        video_usage_key = mocker.Mock()
        video_usage_key.block_type = "video"
        block = mocker.Mock()
        block.usage_key = video_usage_key
        course = mocker.Mock()
        course.language = course_lang

        context = {"block": block, "course": course}
        student_view_context = {}

        step = _make_step(mocker)
        result = step.run_filter(
            context=context,
            student_view_context=student_view_context,
        )

        assert result["student_view_context"]["dest_lang"] == expected_lang

    def test_vertical_block_with_video_children(self, mocker):
        """Test processes video children of vertical blocks."""
        mock_ms = mocker.patch(f"{MODULE}.modulestore")
        mock_video = mocker.Mock()
        mock_video.get_transcripts_info.return_value = {
            "transcripts": {
                "de": "german.srt",
                "en": "english.srt",
            }
        }
        mock_ms.return_value.get_item.return_value = mock_video

        video_child_key = mocker.Mock()
        video_child_key.block_type = "video"
        html_child_key = mocker.Mock()
        html_child_key.block_type = "html"

        vertical_usage_key = mocker.Mock()
        vertical_usage_key.block_type = "vertical"
        block = mocker.Mock()
        block.usage_key = vertical_usage_key
        block.children = [html_child_key, video_child_key]
        course = mocker.Mock()
        course.language = "de"

        context = {"block": block, "course": course}
        student_view_context = {}

        step = _make_step(mocker)
        result = step.run_filter(
            context=context,
            student_view_context=student_view_context,
        )

        assert result["student_view_context"]["dest_lang"] == "de"
        mock_ms.return_value.get_item.assert_called_once_with(video_child_key)

    @pytest.mark.parametrize(
        "children_types",
        [
            (["html", "problem"],),
            (["problem"],),
        ],
    )
    def test_no_processing_without_video(self, mocker, children_types):
        """Test no dest_lang for blocks without video children."""
        mock_ms = mocker.patch(f"{MODULE}.modulestore")

        children = []
        for block_type in children_types[0]:
            child_key = mocker.Mock()
            child_key.block_type = block_type
            children.append(child_key)

        vertical_usage_key = mocker.Mock()
        vertical_usage_key.block_type = "vertical"
        block = mocker.Mock()
        block.usage_key = vertical_usage_key
        block.children = children
        course = mocker.Mock()
        course.language = "fr"

        context = {"block": block, "course": course}
        student_view_context = {}

        step = _make_step(mocker)
        result = step.run_filter(
            context=context,
            student_view_context=student_view_context,
        )

        mock_ms.return_value.get_item.assert_not_called()
        assert "dest_lang" not in result["student_view_context"]

    def test_non_vertical_non_video_block(self, mocker):
        """Test no processing for non-vertical/non-video blocks."""
        mock_ms = mocker.patch(f"{MODULE}.modulestore")

        problem_usage_key = mocker.Mock()
        problem_usage_key.block_type = "problem"
        block = mocker.Mock()
        block.usage_key = problem_usage_key
        course = mocker.Mock()
        course.language = "fr"

        context = {"block": block, "course": course}
        student_view_context = {}

        step = _make_step(mocker)
        result = step.run_filter(
            context=context,
            student_view_context=student_view_context,
        )

        mock_ms.return_value.get_item.assert_not_called()
        assert "dest_lang" not in result["student_view_context"]

    @pytest.mark.parametrize(
        ("course_setup", "transcripts"),
        [
            ("no_language_attr", {"en": "english.srt"}),
            ("has_language", {}),
            ("no_course", {"en": "english.srt"}),
        ],
    )
    def test_defaults_to_english_fallback(self, mocker, course_setup, transcripts):
        """Test defaults to English for various fallback cases."""
        mock_ms = mocker.patch(f"{MODULE}.modulestore")
        mock_video = mocker.Mock()
        mock_video.get_transcripts_info.return_value = (
            {"transcripts": transcripts} if transcripts else {}
        )
        mock_ms.return_value.get_item.return_value = mock_video

        video_usage_key = mocker.Mock()
        video_usage_key.block_type = "video"
        block = mocker.Mock()
        block.usage_key = video_usage_key

        if course_setup == "no_language_attr":
            # spec=[] creates mock without attributes, simulating
            # a course with no language attribute.
            course = mocker.Mock(spec=[])
            context = {"block": block, "course": course}
        elif course_setup == "has_language":
            course = mocker.Mock()
            course.language = "fr"
            context = {"block": block, "course": course}
        else:
            context = {"block": block}

        student_view_context = {}

        step = _make_step(mocker)
        result = step.run_filter(
            context=context,
            student_view_context=student_view_context,
        )

        assert result["student_view_context"]["dest_lang"] == ENGLISH_LANGUAGE_CODE

    def test_returns_context_and_student_view_context(self, mocker):
        """Test returns both context and student_view_context."""
        mocker.patch(f"{MODULE}.modulestore")

        problem_usage_key = mocker.Mock()
        problem_usage_key.block_type = "problem"
        block = mocker.Mock()
        block.usage_key = problem_usage_key
        course = mocker.Mock()
        course.language = "en"

        context = {"block": block, "course": course}
        student_view_context = {"existing_key": "value"}

        step = _make_step(mocker)
        result = step.run_filter(
            context=context,
            student_view_context=student_view_context,
        )

        assert "context" in result
        assert "student_view_context" in result
        assert result["student_view_context"]["existing_key"] == "value"
