"""Tests for showing BlockTranslation rows to learners."""

# ruff: noqa: SLF001

import pytest
from ol_openedx_auto_select_language.translation_filters import (
    TranslateCourseBlockNames,
    TranslateCourseOutline,
)
from ol_openedx_auto_select_language.translations import (
    add_problem_answer_note,
    add_prompt_answer_note,
    plain_key,
    translate_block,
)
from ol_openedx_course_translations.blocks import source_hash
from opaque_keys.edx.keys import CourseKey

API = "ol_openedx_auto_select_language.translations"
FILTERS = "ol_openedx_auto_select_language.translation_filters"
COURSE_KEY = CourseKey.from_string("course-v1:MITx+T101+2026")


class FakeField:
    def __init__(self, name):
        self.name = name

    def _set_cached_value(self, block, value):
        block.cached[self.name] = value


def _block(mocker, block_type="html", block_id="a", **values):
    block = mocker.Mock()
    block.scope_ids.block_type = block_type
    block.scope_ids.usage_id = COURSE_KEY.make_usage_key(block_type, block_id)
    block.cached = {}
    block._dirty_fields = {}
    block.fields = {
        name: FakeField(name) for name in ("data", "display_name", "prompt", "title")
    }
    for name, value in values.items():
        setattr(block, name, value)
    return block


def _translations(block, **fields):
    return {block.scope_ids.usage_id: fields}


@pytest.mark.parametrize(
    ("row_source", "handler", "expected"),
    [
        ("<p>Hello</p>", None, {"data": "<p>Bonjour</p>"}),
        ("<p>Old text</p>", None, {}),
        ("<p>Hello</p>", "peer_assess", {}),
    ],
    ids=["current", "stale_source", "source_text_handler"],
)
def test_translate_block(mocker, row_source, handler, expected):
    block = _block(mocker, block_type="openassessment", data="<p>Hello</p>")
    block.prompt = block.title = block.display_name = None
    mocker.patch(
        f"{API}.course_translations",
        return_value=_translations(
            block, data=(source_hash(row_source), "<p>Bonjour</p>")
        ),
    )
    mocker.patch(f"{API}.TRANSLATABLE_BLOCK_FIELDS", {"openassessment": ("data",)})
    request = mocker.Mock()
    request.resolver_match.kwargs = {"handler": handler} if handler else {}
    mocker.patch(f"{API}.get_current_request", return_value=request)

    translate_block(block)

    assert block.cached == expected


def test_block_names_and_outline_titles(mocker):
    chapter = COURSE_KEY.make_usage_key("chapter", "c1")
    rows = {chapter: {"display_name": (source_hash("Week 1"), "Semaine 1")}}
    mocker.patch(f"{FILTERS}.course_translations", return_value=rows)
    structure = mocker.MagicMock()
    structure.__iter__.return_value = iter([chapter])
    structure.get_xblock_field.return_value = "Week 1"

    TranslateCourseBlockNames(
        filter_type=mocker.Mock(), running_pipeline=mocker.Mock()
    ).run_filter(block_structure=structure, user=None, starting_block_usage_key=chapter)

    structure.override_xblock_field.assert_called_once_with(
        chapter, "display_name", "Semaine 1"
    )

    data = {
        "title": "Course",
        "outline": {"sections": [{"id": str(chapter), "title": "Week 1"}]},
    }
    TranslateCourseOutline(
        filter_type=mocker.Mock(), running_pipeline=mocker.Mock()
    ).run_filter(course_key=COURSE_KEY, user=None, data=data)

    assert data["outline"]["sections"][0]["title"] == "Semaine 1"
    assert data["title"] == "Course"


@pytest.mark.parametrize(
    ("problem", "expects_note"),
    [
        ('<problem><stringresponse answer="a"/></problem>', True),
        ("<problem><multiplechoiceresponse/></problem>", False),
    ],
)
def test_problem_answer_note(mocker, problem, expects_note):
    mocker.patch(f"{API}.get_language", return_value="fr")
    mocker.patch(f"{API}.course_language_name", return_value="English")

    result = add_problem_answer_note(problem, COURSE_KEY)

    assert ("Please enter your answers in English." in result) is expects_note


def test_translate_block_serves_list_fields_without_dirtying(mocker):
    """A List field is served as a list and is not left dirty for save()."""
    answers = [["R", {"label": "Red"}]]
    block = _block(mocker, block_type="poll", answers=answers)
    field = mocker.Mock()
    block.fields = {"answers": field}
    block._dirty_fields = {field: answers}
    translated = '[["R", {"label": "Rouge"}]]'
    mocker.patch(
        f"{API}.course_translations",
        return_value=_translations(block, answers=(source_hash(answers), translated)),
    )
    mocker.patch(f"{API}.TRANSLATABLE_BLOCK_FIELDS", {"poll": ("answers",)})
    mocker.patch(f"{API}.get_current_request", return_value=None)

    translate_block(block)

    field._set_cached_value.assert_called_once_with(block, [["R", {"label": "Rouge"}]])
    assert block._dirty_fields == {}


def test_translate_block_skips_invalid_json(mocker):
    """A malformed stored value is logged and skipped, not raised."""
    answers = [["R", {"label": "Red"}]]
    block = _block(mocker, block_type="poll", answers=answers)
    block.fields = {"answers": mocker.Mock()}
    mocker.patch(
        f"{API}.course_translations",
        return_value=_translations(block, answers=(source_hash(answers), "[oops")),
    )
    mocker.patch(f"{API}.TRANSLATABLE_BLOCK_FIELDS", {"poll": ("answers",)})
    mocker.patch(f"{API}.get_current_request", return_value=None)

    translate_block(block)

    block.fields["answers"]._set_cached_value.assert_not_called()


@pytest.mark.parametrize(
    ("prompt", "check"),
    [
        ("<p>Q</p>", lambda result: result == "NOTE<p>Q</p>"),
        (
            '[{"description": "Q"}]',
            lambda result: result == '[{"description": "NOTEQ"}]',
        ),
        ('[{"description": null}]', lambda result: "NOTE" in result),
        ('"x"', lambda result: result == 'NOTE"x"'),
    ],
    ids=["html", "json_list", "json_null_description", "json_non_list"],
)
def test_prompt_answer_note(mocker, prompt, check):
    mocker.patch(f"{API}.answer_language_note", return_value="NOTE")

    assert check(add_prompt_answer_note(prompt, COURSE_KEY))


def test_plain_key_drops_branch():
    usage_key = COURSE_KEY.for_branch("published-branch").make_usage_key("html", "a")

    assert plain_key(usage_key) == COURSE_KEY.make_usage_key("html", "a")
