"""Tests for the in-place translation filter steps, block rules and backfill."""

# ruff: noqa: SLF001

from datetime import UTC, datetime

import pytest
from ol_openedx_course_translations.api import (
    add_problem_answer_note,
    add_prompt_answer_note,
    plain_key,
    source_hash,
    translate_block,
)
from ol_openedx_course_translations.blocks import restore_capa, restore_kept_parts
from ol_openedx_course_translations.filters import (
    TranslateCourseBlockNames,
    TranslateCourseOutline,
)
from ol_openedx_course_translations.management.commands.backfill_block_translations import (  # noqa: E501
    build_rows,
)
from ol_openedx_course_translations.models import BlockTranslation
from opaque_keys.edx.keys import CourseKey

API = "ol_openedx_course_translations.api"
FILTERS = "ol_openedx_course_translations.filters"
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


SOURCE_PROBLEM = (
    '<problem><p>Capital?</p><stringresponse answer="Paris"><textline/>'
    "</stringresponse><optionresponse><optioninput>"
    '<option correct="True">Red</option><option correct="False">Blue</option>'
    "</optioninput></optionresponse><multiplechoiceresponse>"
    '<choicegroup type="MultipleChoice"><choice correct="true" name="a">Yes</choice>'
    "</choicegroup></multiplechoiceresponse>"
    "<script>x = 1</script></problem>"
)
LLM_PROBLEM = (
    '<problem><p>Capitale ?</p><stringresponse answer="Parigi"><textline/>'
    "</stringresponse><optionresponse><optioninput>"
    '<option correct="Vrai">Rouge</option><option correct="False">Bleu</option>'
    "</optioninput></optionresponse><multiplechoiceresponse>"
    '<choicegroup type="ChoixMultiple"><choice correct="vrai" name="b">Oui</choice>'
    "</choicegroup></multiplechoiceresponse>"
    "<script>x = 2</script></problem>"
)


@pytest.mark.parametrize(
    ("translated", "expected"),
    [
        (
            LLM_PROBLEM,
            SOURCE_PROBLEM.replace("Capital?", "Capitale ?").replace(">Yes<", ">Oui<"),
        ),
        ("<problem><p>Capitale ?</p></problem>", None),
        ("<problem><p>broken", None),
    ],
    ids=["keeps_answers_translates_choices", "structure_differs", "invalid_xml"],
)
def test_restore_capa(translated, expected):
    assert restore_capa(SOURCE_PROBLEM, translated) == expected


@pytest.mark.parametrize(
    ("block_type", "field", "source", "translated", "expected"),
    [
        (
            "poll",
            "answers",
            [["R", {"label": "Red", "img": "r.png"}]],
            '[["X", {"label": "Rouge", "img": "x.png"}]]',
            [["R", {"label": "Rouge", "img": "r.png"}]],
        ),
        (
            "drag-and-drop-v2",
            "data",
            {"zones": [{"title": "Top", "uid": "z1"}, {"title": "Old"}], "items": []},
            (
                '{"zones": [{"title": "Haut", "uid": "zz"}, {"title": "Vieux"}],'
                ' "items": []}'
            ),
            {"zones": [{"title": "Haut", "uid": "z1"}, {"title": "Old"}], "items": []},
        ),
        ("poll", "answers", [["R", {"label": "Red"}]], "[]", None),
    ],
    ids=["poll_keys_kept", "dnd_v1_zone_title_kept", "shape_differs"],
)
def test_restore_kept_parts(block_type, field, source, translated, expected):
    assert restore_kept_parts(block_type, field, source, translated) == expected


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


def test_build_rows_maps_by_block_id_and_flags_stale(mocker):
    translated_at = datetime(2026, 1, 1, tzinfo=UTC)
    edited = _block(
        mocker,
        data="<p>Hi</p>",
        display_name="Intro",
        edited_on=datetime(2026, 2, 1, tzinfo=UTC),
    )
    edited.location = COURSE_KEY.make_usage_key("html", "a")
    untouched = _block(
        mocker,
        data="<p>Same</p>",
        display_name="Same",
        edited_on=datetime(2025, 12, 1, tzinfo=UTC),
    )
    untouched.location = COURSE_KEY.make_usage_key("html", "b")
    missing = _block(mocker, data="x", display_name="x", edited_on=None)
    missing.location = COURSE_KEY.make_usage_key("html", "gone")
    targets = {
        "a": _block(mocker, data="<p>Salut</p>", display_name="Intro"),
        "b": _block(mocker, data="<p>Pareil</p>", display_name="Pareil"),
    }

    rows = build_rows(
        [edited, untouched, missing],
        lambda _type, block_id: targets.get(block_id),
        "fr",
        translated_at,
    )

    assert [(row.field, row.translated_value, row.status) for row in rows] == [
        ("data", "<p>Salut</p>", BlockTranslation.Status.STALE),
        ("display_name", "Pareil", BlockTranslation.Status.AUTO),
        ("data", "<p>Pareil</p>", BlockTranslation.Status.AUTO),
    ]
    assert rows[0].source_hash == source_hash("<p>Hi</p>")


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


def test_restore_capa_drops_added_grading_attributes():
    source = (
        '<problem><choicegroup><choice correct="true">Yes</choice>'
        "<choice>No</choice></choicegroup></problem>"
    )
    translated = (
        '<problem><choicegroup><choice correct="true">Oui</choice>'
        '<choice correct="true">Non</choice></choicegroup></problem>'
    )

    assert restore_capa(source, translated) == (
        '<problem><choicegroup><choice correct="true">Oui</choice>'
        "<choice>Non</choice></choicegroup></problem>"
    )


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
