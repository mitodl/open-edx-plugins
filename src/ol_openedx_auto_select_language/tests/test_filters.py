"""Tests for AddDestLangForVideoBlock filter pipeline step."""

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

    def test_sets_dest_lang_for_matching_transcript(self, mocker):
        """Test dest_lang set for matching transcript."""
        mock_ms = mocker.patch(f"{MODULE}.modulestore")
        mock_video = mocker.Mock()
        mock_video.get_transcripts_info.return_value = {
            "transcripts": {
                "es": "spanish.srt",
                "en": "english.srt",
            }
        }
        mock_ms.return_value.get_item.return_value = mock_video

        video_usage_key = mocker.Mock()
        video_usage_key.block_type = "video"
        block = mocker.Mock()
        block.usage_key = video_usage_key
        course = mocker.Mock()
        course.language = "es"

        context = {"block": block, "course": course}
        student_view_context = {}

        step = _make_step(mocker)
        result = step.run_filter(
            context=context,
            student_view_context=student_view_context,
        )

        assert result["student_view_context"]["dest_lang"] == "es"

    def test_defaults_to_english_no_matching_transcript(self, mocker):
        """Test defaults to English with no matching transcript."""
        mock_ms = mocker.patch(f"{MODULE}.modulestore")
        mock_video = mocker.Mock()
        mock_video.get_transcripts_info.return_value = {
            "transcripts": {"en": "english.srt"}
        }
        mock_ms.return_value.get_item.return_value = mock_video

        video_usage_key = mocker.Mock()
        video_usage_key.block_type = "video"
        block = mocker.Mock()
        block.usage_key = video_usage_key
        course = mocker.Mock()
        course.language = "fr"

        context = {"block": block, "course": course}
        student_view_context = {}

        step = _make_step(mocker)
        result = step.run_filter(
            context=context,
            student_view_context=student_view_context,
        )

        assert result["student_view_context"]["dest_lang"] == ENGLISH_LANGUAGE_CODE

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

    def test_vertical_block_no_video_children(self, mocker):
        """Test no dest_lang for vertical without video children."""
        mock_ms = mocker.patch(f"{MODULE}.modulestore")

        html_child_key = mocker.Mock()
        html_child_key.block_type = "html"
        problem_child_key = mocker.Mock()
        problem_child_key.block_type = "problem"

        vertical_usage_key = mocker.Mock()
        vertical_usage_key.block_type = "vertical"
        block = mocker.Mock()
        block.usage_key = vertical_usage_key
        block.children = [html_child_key, problem_child_key]
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

    def test_converts_django_lang_code_to_bcp47(self, mocker):
        """Test Django-style lang code converted to BCP47."""
        mock_ms = mocker.patch(f"{MODULE}.modulestore")
        mock_video = mocker.Mock()
        mock_video.get_transcripts_info.return_value = {
            "transcripts": {
                "zh-Hans": "chinese.srt",
                "en": "english.srt",
            }
        }
        mock_ms.return_value.get_item.return_value = mock_video

        video_usage_key = mocker.Mock()
        video_usage_key.block_type = "video"
        block = mocker.Mock()
        block.usage_key = video_usage_key
        course = mocker.Mock()
        course.language = "zh_HANS"

        context = {"block": block, "course": course}
        student_view_context = {}

        step = _make_step(mocker)
        result = step.run_filter(
            context=context,
            student_view_context=student_view_context,
        )

        assert result["student_view_context"]["dest_lang"] == "zh-Hans"

    def test_defaults_to_english_no_course_language(self, mocker):
        """Test defaults to English when no course language."""
        mock_ms = mocker.patch(f"{MODULE}.modulestore")
        mock_video = mocker.Mock()
        mock_video.get_transcripts_info.return_value = {
            "transcripts": {"en": "english.srt"}
        }
        mock_ms.return_value.get_item.return_value = mock_video

        video_usage_key = mocker.Mock()
        video_usage_key.block_type = "video"
        block = mocker.Mock()
        block.usage_key = video_usage_key
        course = mocker.Mock(spec=[])

        context = {"block": block, "course": course}
        student_view_context = {}

        step = _make_step(mocker)
        result = step.run_filter(
            context=context,
            student_view_context=student_view_context,
        )

        assert result["student_view_context"]["dest_lang"] == ENGLISH_LANGUAGE_CODE

    def test_defaults_to_english_no_transcripts(self, mocker):
        """Test defaults to English when no transcripts."""
        mock_ms = mocker.patch(f"{MODULE}.modulestore")
        mock_video = mocker.Mock()
        mock_video.get_transcripts_info.return_value = {}
        mock_ms.return_value.get_item.return_value = mock_video

        video_usage_key = mocker.Mock()
        video_usage_key.block_type = "video"
        block = mocker.Mock()
        block.usage_key = video_usage_key
        course = mocker.Mock()
        course.language = "fr"

        context = {"block": block, "course": course}
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

    def test_defaults_to_english_no_course_in_context(self, mocker):
        """Test defaults to English when no course in context."""
        mock_ms = mocker.patch(f"{MODULE}.modulestore")
        mock_video = mocker.Mock()
        mock_video.get_transcripts_info.return_value = {
            "transcripts": {"en": "english.srt"}
        }
        mock_ms.return_value.get_item.return_value = mock_video

        video_usage_key = mocker.Mock()
        video_usage_key.block_type = "video"
        block = mocker.Mock()
        block.usage_key = video_usage_key

        context = {"block": block}
        student_view_context = {}

        step = _make_step(mocker)
        result = step.run_filter(
            context=context,
            student_view_context=student_view_context,
        )

        assert result["student_view_context"]["dest_lang"] == ENGLISH_LANGUAGE_CODE
