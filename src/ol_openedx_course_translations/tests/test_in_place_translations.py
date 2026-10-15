"""Tests for the in-place translation filter step and backfill helpers."""

from datetime import UTC, datetime

import pytest
from ol_openedx_course_translations.api import (
    add_answer_language_note,
    restore_graded_parts,
    source_hash,
)
from ol_openedx_course_translations.filters import (
    TranslateBlockBeforeHandler,
    TranslateVerticalChildContent,
)
from ol_openedx_course_translations.management.commands.backfill_block_translations import (  # noqa: E501
    build_rows,
)
from ol_openedx_course_translations.models import BlockTranslation
from opaque_keys.edx.keys import CourseKey

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
    block.fields = {name: FakeField(name) for name in ("data", "display_name")}
    for name, value in values.items():
        setattr(block, name, value)
    return block


def _step(mocker, step_class, translations, *, enabled=True):
    mocker.patch(f"{FILTERS}.IN_PLACE_TRANSLATIONS.is_enabled", return_value=enabled)
    mocker.patch(f"{FILTERS}.get_language", return_value="fr")
    mocker.patch(f"{FILTERS}.get_translations", return_value=translations)
    mocker.patch(f"{FILTERS}.CourseOverview.get_from_id").return_value.language = "en"
    return step_class(filter_type=mocker.Mock(), running_pipeline=mocker.Mock())


@pytest.mark.parametrize(
    ("enabled", "row_source", "expected"),
    [
        (True, "<p>Hello</p>", {"data": "<p>Bonjour</p>"}),
        (True, "<p>Old text</p>", {}),
        (False, "<p>Hello</p>", {}),
    ],
)
def test_filter_serves_only_current_translations(mocker, enabled, row_source, expected):
    block = _block(mocker, data="<p>Hello</p>")
    translations = {
        block.scope_ids.usage_id: {"data": (source_hash(row_source), "<p>Bonjour</p>")}
    }
    step = _step(mocker, TranslateVerticalChildContent, translations, enabled=enabled)

    result = step.run_filter(block=block, context={})

    assert result["block"] is block
    assert block.cached == expected


def test_filter_translates_library_children_and_before_handlers(mocker):
    child = _block(mocker, block_id="child", data="<p>Hi</p>")
    library = _block(mocker, block_type="itembank", block_id="lib")
    library.get_children.return_value = [child]
    translations = {
        child.scope_ids.usage_id: {"data": (source_hash("<p>Hi</p>"), "<p>Salut</p>")}
    }
    step = _step(mocker, TranslateVerticalChildContent, translations)

    step.run_filter(block=library, context={})

    assert child.cached == {"data": "<p>Salut</p>"}

    child.cached = {}
    handler_step = _step(mocker, TranslateBlockBeforeHandler, translations)
    result = handler_step.run_filter(block=child, handler="xmodule_handler")

    assert result == {"block": child, "handler": "xmodule_handler"}
    assert child.cached == {"data": "<p>Salut</p>"}


SOURCE_PROBLEM = (
    '<problem><p>Capital?</p><stringresponse answer="Paris"><textline/>'
    "</stringresponse><optionresponse><optioninput>"
    '<option correct="True">Red</option><option correct="False">Blue</option>'
    "</optioninput></optionresponse><script>x = 1</script></problem>"
)
LLM_PROBLEM = (
    '<problem><p>Capitale ?</p><stringresponse answer="Parigi"><textline/>'
    "</stringresponse><optionresponse><optioninput>"
    '<option correct="Vrai">Rouge</option><option correct="False">Bleu</option>'
    "</optioninput></optionresponse><script>x = 2</script></problem>"
)


@pytest.mark.parametrize(
    ("translated", "expected"),
    [
        (LLM_PROBLEM, SOURCE_PROBLEM.replace("Capital?", "Capitale ?")),
        ("<problem><p>Capitale ?</p></problem>", None),
        ("<problem><p>broken", None),
    ],
)
def test_restore_graded_parts(translated, expected):
    assert restore_graded_parts(SOURCE_PROBLEM, translated) == expected


@pytest.mark.parametrize(
    ("problem", "expects_note"),
    [
        ('<problem><stringresponse answer="a"/></problem>', True),
        ("<problem><multiplechoiceresponse/></problem>", False),
    ],
)
def test_answer_language_note(mocker, problem, expects_note):
    mocker.patch("ol_openedx_course_translations.api.get_language", return_value="fr")

    result = add_answer_language_note(problem, "en")

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
        ("data", "<p>Pareil</p>", BlockTranslation.Status.AUTO),
        ("display_name", "Pareil", BlockTranslation.Status.AUTO),
    ]
    assert rows[0].source_hash == source_hash("<p>Hi</p>")
