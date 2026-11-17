"""Translation must leave what a problem grades against unchanged."""

from unittest import mock

import pytest
from ol_openedx_course_translations.providers.llm_providers import OpenAIProvider
from ol_openedx_course_translations.utils.constants import ANSWER_PLACEHOLDER
from ol_openedx_course_translations.utils.course_translations import (
    HtmlXmlTranslationHelper,
    keeps_markup_structure,
)

from ol_openedx_course_translations import tasks

CUSTOM_PROBLEM = """<problem>
<customresponse expect="yes">
<p>Type the word yes to agree.</p>
<textline label="Type yes"/>
<answer type="loncapa/python">
correct = ['correct'] if submission[0] == 'yes' else ['incorrect']
</answer>
</customresponse>
</problem>"""

CODE_PROBLEM = """<problem><coderesponse queuename="q"><p>Print the greeting.</p>
<codeparam><grader_payload>{"grader": "ps1/hello.py"}</grader_payload></codeparam>
</coderesponse></problem>"""


def translate(raw, fake_translate):
    """Run the helper's extract/apply round trip with a fake translator."""
    helper = HtmlXmlTranslationHelper(is_xml=True)
    root, units, refs = helper.extract_units(raw)
    root = helper.apply_translations(root, refs, [fake_translate(u) for u in units])
    return units, helper.serialize(root)


def test_grading_code_is_not_sent_for_translation():
    units, _ = translate(CUSTOM_PROBLEM, str)
    code_units, _ = translate(CODE_PROBLEM, str)
    tail_units, _ = translate(
        "<customresponse><answer>x = 1</answer>Explain why.</customresponse>", str
    )

    assert not any("submission" in unit for unit in units)
    assert code_units == ["Print the greeting."]
    # The text after a skipped element belongs to its parent
    assert tail_units == ["Explain why."]


@pytest.mark.parametrize(
    ("translation", "expected_text"),
    [
        ("⟦1⟧, pas ⟦0⟧", "York, pas New York"),
        ("⟦0⟧, pas York", "New York, not York"),
    ],
)
def test_every_answer_is_restored_or_none_is(translation, expected_text):
    raw = (
        '<problem><stringresponse answer="York"><additional_answer answer="New York"/>'
        "<p>New York, not York</p></stringresponse></problem>"
    )

    _, translated = translate(raw, lambda unit: translation if "⟦" in unit else unit)

    assert f"<p>{expected_text}</p>" in translated


@pytest.mark.parametrize(
    ("translation", "expected_text"),
    [
        ("Tapez le mot ⟦0⟧ pour accepter.", "Tapez le mot yes pour accepter."),
        # The LLM dropped the placeholder: the source text stays
        ("Tapez le mot oui pour accepter.", "Type the word yes to agree."),
    ],
)
def test_the_expected_answer_stays_in_the_question_text(translation, expected_text):
    units, translated = translate(
        CUSTOM_PROBLEM, lambda unit: translation if "⟦0⟧" in unit else unit
    )

    assert "Type the word ⟦0⟧ to agree." in units
    assert f"<p>{expected_text}</p>" in translated


@pytest.mark.parametrize(
    ("response", "text", "protected"),
    [
        ('<stringresponse answer="Paris">', "Paris or paris?", "⟦0⟧ or ⟦1⟧?"),
        (
            '<stringresponse answer="York"><additional_answer answer="New York"/>',
            "New York, not York",
            "⟦0⟧, not ⟦1⟧",
        ),
        # The longer answer wins where both start at the same word
        (
            '<stringresponse answer="York"><additional_answer answer="York City"/>',
            "York City",
            "⟦0⟧",
        ),
        # Old OLX: several answers joined by _or_, and an answer as element text
        ('<stringresponse answer="yes_or_no">', "Type yes or no", "Type ⟦0⟧ or ⟦1⟧"),
        (
            (
                '<stringresponse answer="York">'
                "<additional_answer>New York</additional_answer>"
            ),
            "Type New York or York",
            "Type ⟦0⟧ or ⟦1⟧",
        ),
        ('<stringresponse answer="Par.*" type="regexp">', "Paris", "Paris"),
        ('<stringresponse answer="a">', "Pick a city", "Pick a city"),
        ('<stringresponse answer="Paris">', "Parisian food", "Parisian food"),
    ],
)
def test_which_answers_are_protected(response, text, protected):
    raw = f"<problem>{response}<p>{text}</p></stringresponse></problem>"

    units, _ = translate(raw, str)

    assert protected in units


@pytest.mark.parametrize(
    ("candidate", "keeps"),
    [
        (CUSTOM_PROBLEM.replace("Type the word", "Tapez le mot"), True),
        # A validator that translates the answer the question quotes
        (CUSTOM_PROBLEM.replace("the word yes", "le mot oui"), False),
        # ... or quotes in a translatable attribute
        (
            CUSTOM_PROBLEM.replace('label="Type yes"', 'label="Tapez oui"'),
            False,
        ),
        (CUSTOM_PROBLEM.replace('expect="yes"', 'expect="oui"'), False),
        (CUSTOM_PROBLEM.replace("== 'yes'", "== 'oui'"), False),
        (CUSTOM_PROBLEM.replace('<textline label="Type yes"/>', ""), False),
        ("<problem><p>not closed</problem>", False),
    ],
)
def test_keeps_markup_structure(candidate, keeps):
    assert keeps_markup_structure(CUSTOM_PROBLEM, candidate, is_xml=True) is keeps


HTML_PAGE = "<p>Hello there</p><script>var answer = 1;</script>"


@pytest.mark.parametrize(
    ("candidate", "keeps"),
    [
        ("<p>Bonjour</p><script>var answer = 1;</script>", True),
        ("<p>Bonjour</p><script>var answer = 2;</script>", False),
        ("<p>Bonjour</p>", False),
    ],
)
def test_keeps_html_structure(candidate, keeps):
    assert keeps_markup_structure(HTML_PAGE, candidate, is_xml=False) is keeps


@pytest.mark.parametrize(
    ("validated", "saved"),
    [
        # Text-only fix: kept
        (CUSTOM_PROBLEM.replace("Type the word", "Tapez le mot"), True),
        # Grading code commented out: discarded
        (CUSTOM_PROBLEM.replace("<answer", "<!--").replace("</answer>", "-->"), False),
    ],
)
def test_only_a_text_only_validation_is_saved(tmp_path, validated, saved):
    problem = tmp_path / "problem.xml"
    problem.write_text(CUSTOM_PROBLEM, encoding="utf-8")
    provider = mock.Mock()
    provider.translate_text.side_effect = lambda text, *_args, **_kwargs: text
    provider.validate_translation.return_value = validated

    with mock.patch.object(tasks, "get_translation_provider", return_value=provider):
        result = tasks.translate_file_task.run(
            str(problem),
            "en",
            "fr",
            "openai",
            "gpt-5.2",
            "openai",
            "gpt-5.2",
            translation_validation_provider_name="openai",
            translation_validation_model="gpt-5.2",
        )

    assert result["status"] == "success"
    expected = validated if saved else CUSTOM_PROBLEM
    assert problem.read_text(encoding="utf-8") == expected


def test_batched_units_are_told_to_keep_placeholders():
    provider = OpenAIProvider("key", "gpt-5.2")
    with mock.patch.object(
        provider, "_call_llm", return_value=":::0:::\nTapez ⟦0⟧"
    ) as call:
        provider._batch_translate_units(["Type ⟦0⟧"], "fr", None)  # noqa: SLF001

    assert ANSWER_PLACEHOLDER.format(0) in call.call_args.args[0]
