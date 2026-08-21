"""
Tests for HtmlXmlTranslationHelper inline-markup coalescing.

An element whose subtree is only inline formatting tags is extracted as a
single unit so the translator sees the whole sentence. Splitting on tag
boundaries produces broken word order in verb-final languages such as Hindi.
"""

import pytest
from ol_openedx_course_translations.utils.course_translations import (
    HtmlXmlTranslationHelper,
)

MARKUP = (
    "<div>"
    "<li><strong>Understand the basics of linear regression</strong>: "
    "Learn how linear regression models predict a continuous outcome.</li>"
    "<li>Plain item with no inline tags</li>"
    "<p>Text <em>with</em> emphasis and a <a href='/x'>link</a> inside.</p>"
    "</div>"
)


@pytest.fixture
def helper():
    return HtmlXmlTranslationHelper(is_xml=False)


def test_inline_only_element_extracts_as_single_unit(helper):
    _root, units, _refs = helper.extract_units(MARKUP)

    bullet_units = [unit for unit in units if "linear regression" in unit]
    assert len(bullet_units) == 1
    assert "<strong>" in bullet_units[0]
    assert bullet_units[0].endswith("continuous outcome.")

    mixed_units = [unit for unit in units if "emphasis" in unit]
    assert len(mixed_units) == 1
    assert "<em>with</em>" in mixed_units[0]

    assert "Plain item with no inline tags" in units


def test_translation_may_move_tags_and_keeps_attributes(helper):
    root, units, refs = helper.extract_units(MARKUP)

    translated = []
    for unit in units:
        if "linear regression" in unit:
            # A verb-final language moves the bolded phrase to the end.
            translated.append(
                "जानें कि रैखिक प्रतिगमन मॉडल कैसे काम करते हैं: "
                "<strong>रैखिक प्रतिगमन की मूल बातें समझना</strong>"
            )
        elif "emphasis" in unit:
            # The LLM dropped href; the original attribute must be restored.
            translated.append("पाठ <em>साथ</em> और एक <a>कड़ी</a> अंदर।")
        else:
            translated.append(unit)

    output = helper.serialize(helper.apply_translations(root, refs, translated))

    assert "<strong>रैखिक प्रतिगमन की मूल बातें समझना</strong>" in output
    assert 'href="/x"' in output
    assert output.count("<strong>") == 1
    assert output.count("<li>") == 2  # noqa: PLR2004


def test_structure_changing_translation_is_rejected(helper):
    root, units, refs = helper.extract_units(MARKUP)

    translated = [
        "<strong>a</strong><strong>b</strong>" if "linear regression" in unit else unit
        for unit in units
    ]
    output = helper.serialize(helper.apply_translations(root, refs, translated))

    assert "Understand the basics of linear regression" in output
