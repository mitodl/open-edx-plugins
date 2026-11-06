"""Tests for checking that translated problems grade like their source."""

from types import SimpleNamespace

import pytest
from django.utils import translation
from ol_openedx_course_translations.grading import capa_module, grades_like_source
from opaque_keys.edx.keys import CourseKey

COURSE_KEY = CourseKey.from_string("course-v1:MITx+T101+2026")


@pytest.mark.parametrize(
    ("extracted", "installed", "expected"),
    [
        (True, {"xblocks_contrib", "xmodule"}, "xblocks_contrib"),
        (False, {"xblocks_contrib", "xmodule"}, "xmodule"),
        (False, {"xblocks_contrib"}, "xblocks_contrib"),
        (True, {"xmodule"}, "xmodule"),
    ],
)
def test_capa_module_follows_the_problem_block_in_use(
    mocker, settings, extracted, installed, expected
):
    """Capa classes come from the package of the problem block the platform runs."""
    settings.USE_EXTRACTED_PROBLEM_BLOCK = extracted

    def import_module(name):
        if name.split(".")[0] not in installed:
            raise ImportError(name)
        return name

    mocker.patch(
        "ol_openedx_course_translations.grading.import_module", import_module
    )

    assert capa_module("responsetypes").split(".")[0] == expected

SOURCE = """<problem>
<multiplechoiceresponse>
<label>Which planet is closest to the Sun?</label>
<choicegroup type="MultipleChoice">
<choice correct="false">Venus</choice>
<choice correct="true">Mercury</choice>
</choicegroup>
</multiplechoiceresponse>
<stringresponse answer="Paris" type="ci">
<label>Capital of France?</label>
<textline size="20"/>
</stringresponse>
<numericalresponse answer="4">
<label>2 + 2?</label>
<formulaequationinput/>
</numericalresponse>
</problem>"""

TRANSLATED = (
    SOURCE.replace(
        "Which planet is closest to the Sun?", "Quelle planète est la plus proche ?"
    )
    .replace(">Venus<", ">Vénus<")
    .replace(">Mercury<", ">Mercure<")
    .replace("Capital of France?", "Capitale de la France ?")
)


def _block():
    runtime = SimpleNamespace(
        service=lambda _block, _name: translation, resources_fs=None
    )
    return SimpleNamespace(
        location=COURSE_KEY.make_usage_key("problem", "p1"),
        runtime=runtime,
        data=SOURCE,
    )


@pytest.mark.parametrize(
    ("translated", "expected"),
    [
        (TRANSLATED, True),
        (
            TRANSLATED.replace('"false">Vénus', '"true">Vénus').replace(
                '"true">Mercure', '"false">Mercure'
            ),
            False,
        ),
        (TRANSLATED.replace('answer="Paris"', 'answer="Paris, France"'), False),
        (TRANSLATED.replace('answer="4"', 'answer="5"'), False),
        (TRANSLATED.replace("<stringresponse", "<stringresponse_"), False),
    ],
    ids=["text_only", "correct_choice_moved", "typed_answer", "number", "unparseable"],
)
def test_grades_like_source(translated, expected):
    assert grades_like_source(_block(), translated) is expected


@pytest.mark.parametrize(
    ("translated", "grades", "expected"),
    [
        (TRANSLATED, ValueError("not a submission"), True),
        (
            TRANSLATED.replace('answer="Paris"', 'answer="Lyon"'),
            ValueError("not a submission"),
            False,
        ),
        (TRANSLATED, [{"a": "correct"}, ValueError("broken")], False),
    ],
    ids=["source_cannot_grade_answers_match", "answers_differ", "translation_fails"],
)
def test_grades_like_source_when_grading_raises(mocker, translated, grades, expected):
    mocker.patch("ol_openedx_course_translations.grading._grades", side_effect=grades)

    assert grades_like_source(_block(), translated) is expected
