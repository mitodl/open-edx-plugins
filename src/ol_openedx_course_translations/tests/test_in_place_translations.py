"""Tests for the block translation rules and the backfill command."""

from datetime import UTC, datetime

import pytest
from ol_openedx_course_translations.blocks import (
    restore_capa,
    restore_kept_parts,
    source_hash,
)
from ol_openedx_course_translations.management.commands.backfill_block_translations import (  # noqa: E501
    build_rows,
)
from ol_openedx_course_translations.models import BlockTranslation
from opaque_keys.edx.keys import CourseKey

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
