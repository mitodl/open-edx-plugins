"""Tests for the block translation rules and the backfill command."""

from datetime import UTC, datetime

import pytest
from ol_openedx_course_translations.blocks import (
    restore_capa,
    restore_kept_parts,
    serialize,
    source_hash,
)
from ol_openedx_course_translations.management.commands.backfill_block_translations import (  # noqa: E501
    build_rows,
)
from ol_openedx_course_translations.management.commands.translate_blocks_in_place import (  # noqa: E501
    translate_value,
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
        (
            SOURCE_PROBLEM.replace(
                "<textline/></stringresponse>", "</stringresponse><textline/>"
            ),
            None,
        ),
        ("<problem><p>broken", None),
        (
            (
                '<!DOCTYPE p [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
                "<problem><p>&x;</p></problem>"
            ),
            None,
        ),
    ],
    ids=[
        "keeps_answers_translates_choices",
        "structure_differs",
        "element_moved",
        "invalid_xml",
        "external_entity_not_expanded",
    ],
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
        (
            "survey",
            "answers",
            [("Y", "Yes"), ("N", "No")],
            '[["Y", "Oui"], ["N", "Non"]]',
            [["Y", "Oui"], ["N", "Non"]],
        ),
        (
            "drag-and-drop-v2",
            "data",
            {"feedback": {"start": "Drag", "finish": "Done"}},
            '{"feedback": {"start": "Glissez", "finish": "Fini"}}',
            {"feedback": {"start": "Glissez", "finish": "Fini"}},
        ),
        (
            "openassessment",
            "rubric_criteria",
            [{"name": "c1", "label": "Ideas", "feedback": "optional"}],
            '[{"name": "x", "label": "Idees", "feedback": "facultatif"}]',
            [{"name": "c1", "label": "Idees", "feedback": "optional"}],
        ),
        ("poll", "answers", [["R", {"label": "Red"}]], "[]", None),
        (
            "poll",
            "answers",
            [["R", {"label": "Red"}], ["B", {"label": "Blue"}]],
            '[["B", {"label": "Bleu"}], ["R", {"label": "Rouge"}]]',
            None,
        ),
        (
            "openassessment",
            "rubric_criteria",
            [
                {"name": "ideas", "label": "Ideas", "options": []},
                {"name": "grammar", "label": "Grammar", "options": []},
            ],
            (
                '[{"name": "grammar", "label": "Grammaire", "options": []},'
                ' {"name": "ideas", "label": "Idees", "options": []}]'
            ),
            None,
        ),
        (
            "openassessment",
            "rubric_criteria",
            [
                {
                    "name": "ideas",
                    "label": "Ideas",
                    "options": [
                        {"name": "poor", "label": "Poor", "points": 0},
                        {"name": "good", "label": "Good", "points": 2},
                    ],
                }
            ],
            (
                '[{"name": "ideas", "label": "Idees", "options": ['
                '{"name": "good", "label": "Bien", "points": 2},'
                ' {"name": "poor", "label": "Faible", "points": 0}]}]'
            ),
            None,
        ),
        (
            "poll_question",
            "answers",
            [{"id": "R", "text": "Red"}, {"id": "B", "text": "Blue"}],
            '[{"id": "B", "text": "Bleu"}, {"id": "R", "text": "Rouge"}]',
            None,
        ),
        (
            "openassessment",
            "prompt",
            '[{"description": "One"}, {"description": "Two"}]',
            '[{"description": "Un"}, {"description": "Deux"}]',
            '[{"description": "Un"}, {"description": "Deux"}]',
        ),
        (
            "openassessment",
            "prompt",
            '[{"description": "One"}, {"description": "Two"}]',
            '[{"descripción": "Un"}, {"description": "Deux"}]',
            None,
        ),
        ("openassessment", "prompt", "<p>One</p>", "<p>Un</p>", "<p>Un</p>"),
    ],
    ids=[
        "poll_keys_kept",
        "dnd_v1_zone_title_kept",
        "tuple_pairs",
        "dnd_feedback_messages_translated",
        "ora_feedback_setting_kept",
        "shape_differs",
        "reordered_pairs",
        "reordered_ora_criteria",
        "reordered_ora_options",
        "reordered_id_entries",
        "ora_prompts_json",
        "ora_prompts_key_changed",
        "ora_single_prompt",
    ],
)
def test_restore_kept_parts(block_type, field, source, translated, expected):
    assert restore_kept_parts(block_type, field, source, translated) == expected


def test_build_rows_maps_by_block_id_and_flags_stale(mocker):
    imported = datetime(2026, 1, 1, tzinfo=UTC)
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
        "a": _block(
            mocker, data="<p>Salut</p>", display_name="Intro", edited_on=imported
        ),
        "b": _block(
            mocker, data="<p>Pareil</p>", display_name="Pareil", edited_on=imported
        ),
    }

    rows = build_rows(
        [edited, untouched, missing],
        lambda _type, block_id: targets.get(block_id),
        "fr",
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


class FakeProvider:
    """Upper-cases text, like a translation that changes every string."""

    def translate_text(self, source_text, _target_language, tag_handling=None):
        self.tag_handling = tag_handling
        return source_text.replace("Question", "QUESTION")

    def _batch_translate_units(self, units, _target_language, _glossary_directory):
        return [unit.upper() for unit in units]


@pytest.mark.parametrize(
    ("block_type", "field", "source", "expected", "tag_handling"),
    [
        ("html", "data", "<p>Question</p>", "<p>QUESTION</p>", "html"),
        (
            "problem",
            "data",
            "<problem>Question</problem>",
            "<problem>QUESTION</problem>",
            "xml",
        ),
        ("poll", "question", "Question", "QUESTION", None),
        (
            "poll",
            "answers",
            [("R", {"label": "Red", "img": None})],
            [["R", {"label": "RED", "img": None}]],
            None,
        ),
        (
            "openassessment",
            "prompt",
            '[{"description": "One"}, {"description": "Two"}]',
            '[{"description": "ONE"}, {"description": "TWO"}]',
            None,
        ),
    ],
    ids=["html", "capa_xml", "plain", "nested_keys_restored", "ora_prompts_json"],
)
def test_translate_value(block_type, field, source, expected, tag_handling):
    provider = FakeProvider()

    translated = translate_value(provider, block_type, field, source, "fr")
    restored = restore_kept_parts(block_type, field, source, serialize(translated))

    assert restored == expected
    assert getattr(provider, "tag_handling", None) == tag_handling


class MarkupProvider(FakeProvider):
    """Records which strings went through the markup-aware path."""

    def translate_text(self, source_text, _target_language, tag_handling=None):
        self.tag_handling = tag_handling
        return source_text.replace("Note", "NOTE")


def test_translate_value_nested_markup_uses_markup_path():
    provider = MarkupProvider()
    source = [{"id": 1, "content": '<p><a href="/x">Note</a></p>', "date": "d"}]

    translated = translate_value(provider, "course_info", "items", source, "fr")

    # Markup goes through translate_text; plain strings through the batch API.
    assert translated == [
        {"id": 1, "content": '<p><a href="/x">NOTE</a></p>', "date": "D"}
    ]
    assert provider.tag_handling == "html"


def test_restore_capa_rejects_reordered_choices():
    source = (
        '<problem><choicegroup><choice correct="true" name="yes">Yes</choice>'
        '<choice correct="false" name="no">No</choice></choicegroup></problem>'
    )
    translated = (
        '<problem><choicegroup><choice correct="false" name="no">Non</choice>'
        '<choice correct="true" name="yes">Oui</choice></choicegroup></problem>'
    )

    assert restore_capa(source, translated) is None


def test_restore_capa_keeps_typed_answer_translated_by_mistake():
    source = (
        '<problem><stringresponse answer="dog"><textline/></stringresponse></problem>'
    )
    translated = (
        '<problem><stringresponse answer="chien"><textline/></stringresponse></problem>'
    )

    assert restore_capa(source, translated) == source


def test_admin_saves_the_hash_of_the_source_it_validated(mocker):
    from django.contrib import admin  # noqa: PLC0415
    from ol_openedx_course_translations.admin import (  # noqa: PLC0415
        BlockTranslationAdmin,
        BlockTranslationForm,
    )

    usage_key = COURSE_KEY.make_usage_key("html", "a")
    row = BlockTranslation(
        course_key=COURSE_KEY, usage_key=usage_key, field="display_name", language="fr"
    )
    published = mocker.patch(
        "ol_openedx_course_translations.admin.published_source_value",
        side_effect=["Old title", "New title"],
    )
    mocker.patch.object(admin.ModelAdmin, "save_model")
    form = BlockTranslationForm(instance=row)
    form.cleaned_data = {"translated_value": "Titre"}
    form.changed_data = ["translated_value"]

    form.clean_translated_value()
    # The course is published again before the row is saved.
    BlockTranslationAdmin(BlockTranslation, admin.site).save_model(
        None, row, form, change=True
    )

    assert row.source_hash == source_hash("Old title")
    assert row.status == BlockTranslation.Status.REVIEWED
    assert published.call_count == 1


@pytest.mark.django_db
def test_translate_blocks_in_place_saves_rows_before_a_provider_error(mocker):
    from django.core.management import call_command  # noqa: PLC0415

    command = (
        "ol_openedx_course_translations.management.commands.translate_blocks_in_place"
    )
    blocks = [
        _block(mocker, block_id=name, display_name=name.title()) for name in ("a", "b")
    ]
    for block in blocks:
        block.location = block.scope_ids.usage_id
    store = mocker.Mock()
    store.get_items.side_effect = lambda _key, qualifiers, **_kw: (
        blocks if qualifiers["category"] == "html" else []
    )
    mocker.patch("xmodule.modulestore.django.modulestore", return_value=store)
    mocker.patch(f"{command}.parse_and_validate_provider_spec", return_value=("p", "m"))
    mocker.patch(f"{command}.get_translation_provider")
    first_row = mocker.Mock()
    mocker.patch(
        f"{command}.translated_row", side_effect=[first_row, RuntimeError("API error")]
    )
    save_rows = mocker.patch(f"{command}.save_rows", return_value=1)

    with pytest.raises(RuntimeError):
        call_command(
            "translate_blocks_in_place",
            course=str(COURSE_KEY),
            language="fr",
            provider="p/m",
        )

    save_rows.assert_called_once_with([first_row])
