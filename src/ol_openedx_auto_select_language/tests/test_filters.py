"""Tests for the auto-select-language filter pipeline steps."""

from collections import OrderedDict

import pytest
from ol_openedx_auto_select_language.constants import (
    ENGLISH_LANGUAGE_CODE,
)
from ol_openedx_auto_select_language.filters import (
    AddDestLangForVideoBlock,
    RestrictVideoTranscriptLanguages,
)

MODULE = "ol_openedx_auto_select_language.filters"

ALL_LANGUAGES = OrderedDict([("en", "English"), ("es", "Español"), ("fr", "Français")])


def _make_step(mocker):
    """Create an AddDestLangForVideoBlock step with mock args."""
    return AddDestLangForVideoBlock(
        filter_type=mocker.Mock(),
        running_pipeline=mocker.Mock(),
    )


@pytest.mark.parametrize(
    ("course_lang", "transcripts", "expected_lang"),
    [
        (
            "es",
            {"es": "spanish.srt", "en": "english.srt"},
            "es",
        ),
        (
            "es_419",
            {"es-419": "spanish.srt", "en": "english.srt"},
            "es-419",
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


@pytest.mark.parametrize(
    ("block_type", "children_types", "course_lang", "transcripts", "expected_lang"),
    [
        (
            "vertical",
            ["html", "video"],
            "de",
            {"de": "german.srt", "en": "english.srt"},
            "de",
        ),
        (
            "vertical",
            ["html", "problem"],
            "fr",
            None,
            None,
        ),
        (
            "vertical",
            ["problem"],
            "fr",
            None,
            None,
        ),
        (
            "problem",
            None,
            "fr",
            None,
            None,
        ),
    ],
)
def test_non_video_block_dest_lang(  # noqa: PLR0913, PLR0917
    mocker,
    block_type,
    children_types,
    course_lang,
    transcripts,
    expected_lang,
):
    """Test dest_lang for vertical/non-video blocks and their children."""
    mock_ms = mocker.patch(f"{MODULE}.modulestore")
    if transcripts is not None:
        mock_video = mocker.Mock()
        mock_video.get_transcripts_info.return_value = {"transcripts": transcripts}
        mock_ms.return_value.get_item.return_value = mock_video

    usage_key = mocker.Mock()
    usage_key.block_type = block_type
    block = mocker.Mock()
    block.usage_key = usage_key
    if children_types is not None:
        children = []
        for ct in children_types:
            child_key = mocker.Mock()
            child_key.block_type = ct
            children.append(child_key)
        block.children = children
    course = mocker.Mock()
    course.language = course_lang

    context = {"block": block, "course": course}
    student_view_context = {}

    step = _make_step(mocker)
    result = step.run_filter(
        context=context,
        student_view_context=student_view_context,
    )

    if expected_lang is not None:
        video_child = next(
            child for child in block.children if child.block_type == "video"
        )
        mock_ms.return_value.get_item.assert_called_once_with(video_child)
        assert result["student_view_context"]["dest_lang"] == expected_lang
    else:
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
def test_transcript_defaults_to_english_fallback(mocker, course_setup, transcripts):
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


def test_returns_context_and_student_view_context(mocker):
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


def _patch_course_language(mocker, language):
    """Make the block's course report `language` to the restriction step."""
    overview = mocker.patch(f"{MODULE}.CourseOverview")
    overview.get_from_id.return_value = mocker.Mock(language=language)
    return overview


def _make_restrict_step(mocker):
    """Create a RestrictVideoTranscriptLanguages step with mock args."""
    return RestrictVideoTranscriptLanguages(
        filter_type=mocker.Mock(),
        running_pipeline=mocker.Mock(),
    )


def _make_video_block(mocker, language="es", languages=None):
    """Build a mock video block whose transcript method returns known values."""
    block = mocker.Mock()
    block.scope_ids.block_type = "video"
    block.ol_transcripts_restricted = False
    block.get_transcripts_for_student = mocker.Mock(
        return_value=(
            "http://example.com/transcript",
            language,
            ALL_LANGUAGES if languages is None else languages,
        )
    )
    return block


@pytest.mark.parametrize(
    ("course_language", "resolved", "languages", "expected"),
    [
        # The course language has a transcript: the menu collapses to it.
        ("es", "es", ALL_LANGUAGES, {"es": "Español"}),
        # pt-BR legitimately resolves to pt, which still counts as a match.
        (
            "pt-BR",
            "pt",
            OrderedDict([("en", "English"), ("pt", "Português")]),
            {"pt": "Português"},
        ),
        # No transcript in the course language: the platform falls back, and
        # the full menu survives rather than being pinned to the fallback.
        ("en", "es", ALL_LANGUAGES, ALL_LANGUAGES),
        (
            "es",
            "en",
            OrderedDict([("en", "English"), ("fr", "Français")]),
            OrderedDict([("en", "English"), ("fr", "Français")]),
        ),
        # The resolved language has no label, so narrowing would empty the menu.
        ("de", "de", ALL_LANGUAGES, ALL_LANGUAGES),
    ],
    ids=["exact", "generalized", "fallback", "course_language_absent", "unlabeled"],
)
def test_language_restriction(  # noqa: PLR0913, PLR0917
    mocker, settings, course_language, resolved, languages, expected
):
    """Only a transcript in the course language narrows the player's menu."""
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = True
    _patch_course_language(mocker, course_language)
    block = _make_video_block(mocker, language=resolved, languages=languages)

    _make_restrict_step(mocker).run_filter(block=block, context={})

    _, _, result = block.get_transcripts_for_student(
        transcripts={"sub": "", "transcripts": {}}, dest_lang="en"
    )

    assert result == expected


@pytest.mark.parametrize(
    ("block_type", "has_transcript_method", "flag"),
    [
        ("problem", True, True),
        ("video", True, False),
        ("video", True, None),
        ("video", False, True),
    ],
    ids=["non_video", "flag_disabled", "flag_undefined", "no_transcript_method"],
)
def test_step_declines_to_wrap(
    mocker, settings, block_type, has_transcript_method, flag
):
    """The block keeps its own method when the step has no business wrapping."""
    if flag is None:
        # A deployment that never defined the setting at all.
        if hasattr(settings, "ENABLE_AUTO_LANGUAGE_SELECTION"):
            del settings.ENABLE_AUTO_LANGUAGE_SELECTION
    else:
        settings.ENABLE_AUTO_LANGUAGE_SELECTION = flag
    _patch_course_language(mocker, "es")
    if has_transcript_method:
        block = _make_video_block(mocker)
    else:
        # HiddenBlock stands in for a disabled video type, keeping block_type.
        block = mocker.Mock(spec=["scope_ids"])
    block.scope_ids.block_type = block_type
    original = getattr(block, "get_transcripts_for_student", None)

    result = _make_restrict_step(mocker).run_filter(block=block, context={})

    assert result == {"block": block, "context": {}}
    assert getattr(block, "get_transcripts_for_student", None) is original


def test_applying_twice_does_not_stack_wrappers(mocker, settings):
    """Re-running the step on the same instance rewraps nothing."""
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = True
    _patch_course_language(mocker, "es")
    block = _make_video_block(mocker)
    step = _make_restrict_step(mocker)

    step.run_filter(block=block, context={})
    wrapped_once = block.get_transcripts_for_student
    step.run_filter(block=block, context={})

    assert block.get_transcripts_for_student is wrapped_once


def test_real_video_block_is_not_dirtied(mocker, settings):
    """The instance override must not mark the real XBlock dirty."""
    from opaque_keys.edx.locator import CourseLocator  # noqa: PLC0415
    from xblock.field_data import DictFieldData  # noqa: PLC0415
    from xblock.fields import ScopeIds  # noqa: PLC0415
    from xmodule.tests import get_test_descriptor_system  # noqa: PLC0415
    from xmodule.video_block.video_block import VideoBlock  # noqa: PLC0415

    settings.ENABLE_AUTO_LANGUAGE_SELECTION = True
    _patch_course_language(mocker, "es")
    course_key = CourseLocator("org", "course", "run")
    usage_key = course_key.make_usage_key("video", "SampleVideo")
    block = get_test_descriptor_system().construct_xblock_from_class(
        VideoBlock,
        scope_ids=ScopeIds(None, "video", usage_key, usage_key),
        field_data=DictFieldData(
            {"transcripts": {"es": "es.srt", "fr": "fr.srt"}, "sub": "sample"}
        ),
    )

    transcripts_info = block.get_transcripts_info()
    dirty_before = dict(block._dirty_fields)  # noqa: SLF001

    RestrictVideoTranscriptLanguages(filter_type="t", running_pipeline=[]).run_filter(
        block=block, context={}
    )

    _, language, languages = block.get_transcripts_for_student(
        transcripts=transcripts_info, dest_lang="es"
    )

    assert language == "es"
    assert list(languages) == ["es"]
    # XBlock marks mutable Dict fields dirty on read, so the invariant that
    # matters is that the step adds nothing of its own.
    assert dict(block._dirty_fields) == dirty_before  # noqa: SLF001


def test_resolves_with_course_language_not_shared_dest_lang(mocker, settings):
    """A sibling video must not drag this one off the course language."""
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = True
    _patch_course_language(mocker, "es")
    languages = OrderedDict([("en", "English"), ("es", "Español")])

    def resolver(transcripts, dest_lang=None):
        """Stand in for get_default_transcript_language's fallback chain."""
        resolved = dest_lang if dest_lang in transcripts["transcripts"] else "en"
        return ("http://example.com/transcript", resolved, languages)

    block = mocker.Mock()
    block.scope_ids.block_type = "video"
    block.ol_transcripts_restricted = False
    block.get_transcripts_for_student = mocker.Mock(side_effect=resolver)

    _make_restrict_step(mocker).run_filter(block=block, context={})

    # dest_lang arrives as "en" because another video in the same vertical
    # overwrote the shared student_view_context key.
    _, language, result = block.get_transcripts_for_student(
        transcripts={"sub": "", "transcripts": {"es": "es.srt", "en": "en.srt"}},
        dest_lang="en",
    )

    assert language == "es"
    assert result == {"es": "Español"}
