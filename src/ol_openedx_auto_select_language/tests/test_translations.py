"""Tests for showing BlockTranslation rows to learners."""

# ruff: noqa: SLF001

import pytest
from ol_openedx_auto_select_language.translation_filters import (
    AddAnswerNoteBelowTitles,
    TranslateCourseBlockNames,
    TranslateCourseNavigationAssignmentTypes,
    TranslateCourseOutline,
    TranslateCoursewareMetadata,
    TranslateDatesAssignmentTypes,
    TranslateOutlineTabAssignmentTypes,
    TranslateProgressAssignmentTypes,
)
from ol_openedx_auto_select_language.translations import (
    add_problem_answer_note,
    grader_labels,
    plain_key,
    refresh_problem_feedback,
    responsetypes,
    translate_block,
)
from ol_openedx_course_translations.blocks import (
    GRADER_LABELS_FIELD,
    serialize,
    source_hash,
)
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
    ("row_source", "handler", "path", "expected"),
    [
        ("<p>Hello</p>", None, "/xblock/x", {"data": "<p>Bonjour</p>"}),
        ("<p>Old text</p>", None, "/xblock/x", {}),
        ("<p>Hello</p>", "peer_assess", "/xblock/x", {}),
        ("<p>Hello</p>", None, "/api/ora_staff_grader/submission/grade", {}),
    ],
    ids=["current", "stale_source", "source_text_handler", "staff_grader"],
)
def test_translate_block(mocker, row_source, handler, path, expected):
    block = _block(mocker, block_type="openassessment", data="<p>Hello</p>")
    block.prompt = block.title = block.display_name = None
    mocker.patch(
        f"{API}.course_translations",
        return_value=_translations(
            block, data=(source_hash(row_source), "<p>Bonjour</p>")
        ),
    )
    mocker.patch(f"{API}.TRANSLATABLE_BLOCK_FIELDS", {"openassessment": ("data",)})
    request = mocker.Mock(path=path)
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


def test_plain_key_drops_branch():
    usage_key = COURSE_KEY.for_branch("published-branch").make_usage_key("html", "a")

    assert plain_key(usage_key) == COURSE_KEY.make_usage_key("html", "a")


def test_answer_note_below_ora_title(mocker):
    """The note goes right after a translated ORA's title, not other blocks'."""
    ora = COURSE_KEY.make_usage_key("openassessment", "o1")
    other = COURSE_KEY.make_usage_key("openassessment", "o2")
    mocker.patch(f"{FILTERS}.course_translations", return_value={ora: {"title": "x"}})
    mocker.patch(f"{FILTERS}.answer_language_note", return_value="<NOTE>")
    title = '<h3 class="openassessment__title problem__header">Essay</h3>'
    unit = mocker.Mock()
    unit.scope_ids.usage_id = COURSE_KEY.make_usage_key("vertical", "v")
    unit.children = [ora, other]
    fragment = mocker.Mock()
    fragment.content = (
        f'<div data-id="{ora}">{title}<p>Prompt</p></div>'
        f'<div data-id="{other}">{title}</div>'
    )

    AddAnswerNoteBelowTitles(
        filter_type=mocker.Mock(), running_pipeline=mocker.Mock()
    ).run_filter(block=unit, fragment=fragment, context={}, view="student_view")

    assert fragment.content == (
        f'<div data-id="{ora}">{title}<NOTE><p>Prompt</p></div>'
        f'<div data-id="{other}">{title}</div>'
    )


def test_translate_block_restores_source_before_rebinding(mocker):
    """A block bound again (another user, a source handler) starts from source."""
    block = _block(mocker, data="<p>Hello</p>")
    rows = {"data": (source_hash("<p>Hello</p>"), "<p>Bonjour</p>")}
    patched = mocker.patch(
        f"{API}.course_translations", return_value=_translations(block, **rows)
    )
    mocker.patch(f"{API}.get_current_request", return_value=None)
    block.fields["data"]._set_cached_value = lambda b, v: setattr(b, "data", v)

    translate_block(block)
    assert block.data == "<p>Bonjour</p>"

    patched.return_value = {}
    translate_block(block)
    assert block.data == "<p>Hello</p>"


def _correct_map(msg):
    correct_map = responsetypes.CorrectMap()
    correct_map.set("p_2_1", correctness="correct", npoints=1, msg=msg)
    return correct_map


def _problem(mocker, responder, saved_msg="<p>Exact</p>"):
    block = mocker.Mock()
    block.scope_ids.block_type = "problem"
    block.scope_ids.usage_id = COURSE_KEY.make_usage_key("problem", "p")
    block.correct_map = {"p_2_1": {"msg": saved_msg}}
    block.has_saved_answers = False
    block.lcp.student_answers = {"p_2_1": "choice_0"}
    block.lcp.responders = {"r": responder}
    block.lcp.correct_map = _correct_map(saved_msg)
    block.fields = {"correct_map": mocker.Mock()}
    block._dirty_fields = {}
    return block


def _responder(
    mocker,
    response_class,
    rebuilt_msg="<p>Right</p>",
    hintfn=None,
    rebuilt_correctness="correct",
):
    responder = mocker.Mock(spec=response_class)
    responder.answer_ids = ["p_2_1"]
    responder.xml = mocker.Mock()
    responder.xml.find.return_value = (
        mocker.Mock(get=lambda _name: hintfn) if hintfn else None
    )
    rebuilt = _correct_map(rebuilt_msg)
    rebuilt.set_property("p_2_1", "correctness", rebuilt_correctness)
    responder.evaluate_answers.return_value = rebuilt
    return responder


@pytest.mark.parametrize(
    ("response_class", "hintfn", "enabled", "expected_msg"),
    [
        (responsetypes.MultipleChoiceResponse, None, True, "<p>Right</p>"),
        (responsetypes.ChoiceResponse, None, True, "<p>Right</p>"),
        (responsetypes.CustomResponse, None, True, "<p>Exact</p>"),
        (responsetypes.OptionResponse, "hint_fn", True, "<p>Exact</p>"),
        (responsetypes.MultipleChoiceResponse, None, False, "<p>Exact</p>"),
    ],
    ids=[
        "choice_feedback_rebuilt",
        "checkbox_feedback_rebuilt",
        "course_code_response_kept",
        "hint_function_kept",
        "flag_off_kept",
    ],
)
def test_refresh_problem_feedback(
    mocker, response_class, hintfn, enabled, expected_msg
):
    mocker.patch(f"{API}.in_place_translations_enabled", return_value=enabled)
    block = _problem(mocker, _responder(mocker, response_class, hintfn=hintfn))

    refresh_problem_feedback(block)

    assert block.lcp.correct_map.get_msg("p_2_1") == expected_msg
    # Only feedback is rebuilt; the saved grading is kept.
    assert block.lcp.correct_map.get_correctness("p_2_1") == "correct"
    # The problem is built again from the state after a later bind.
    if enabled:
        set_cached = block.fields["correct_map"]._set_cached_value
        set_cached.assert_called_once_with(block, block.lcp.correct_map.get_dict())
        assert set_cached.call_args.args[1]["p_2_1"]["msg"] == expected_msg


def test_refresh_problem_feedback_publishes_no_events(mocker):
    class Runtime:
        def __init__(self):
            self.events = []

        def publish(self, _block, name, _data):
            self.events.append(name)

    mocker.patch(f"{API}.in_place_translations_enabled", return_value=True)
    responder = _responder(mocker, responsetypes.MultipleChoiceResponse)
    block = _problem(mocker, responder)
    block.runtime = Runtime()
    rebuilt = responder.evaluate_answers.return_value

    def evaluate(*_args):
        block.runtime.publish(block, "edx.problem.hint.feedback_displayed", {})
        return rebuilt

    responder.evaluate_answers.side_effect = evaluate

    refresh_problem_feedback(block)
    block.runtime.publish(block, "later", {})

    assert block.runtime.events == ["later"]


def test_refresh_problem_feedback_keeps_saved_feedback_on_error(mocker):
    mocker.patch(f"{API}.in_place_translations_enabled", return_value=True)
    responder = _responder(mocker, responsetypes.StringResponse)
    responder.evaluate_answers.side_effect = ValueError("bad answer")
    block = _problem(mocker, responder)

    refresh_problem_feedback(block)

    assert block.lcp.correct_map.get_msg("p_2_1") == "<p>Exact</p>"


def test_refresh_problem_feedback_skips_saved_unsubmitted_answers(mocker):
    mocker.patch(f"{API}.in_place_translations_enabled", return_value=True)
    responder = _responder(mocker, responsetypes.MultipleChoiceResponse)
    block = _problem(mocker, responder)
    block.has_saved_answers = True

    refresh_problem_feedback(block)

    responder.evaluate_answers.assert_not_called()
    assert block.lcp.correct_map.get_msg("p_2_1") == "<p>Exact</p>"


GRADERS = [["Homework", "HW"], ["Exam", "Ex"]]
LABELS = {
    "Homework": {"type": "Devoirs", "short_label": "DEV"},
    "Exam": {"type": "Examen", "short_label": "EX"},
}


@pytest.mark.parametrize(
    ("row_hash", "expected"),
    [(source_hash(GRADERS), LABELS), ("old", {}), (None, {})],
    ids=["current", "grading_changed", "no_row"],
)
def test_grader_labels(mocker, row_hash, expected):
    course_usage_key = COURSE_KEY.make_usage_key("course", "course")
    rows = (
        {course_usage_key: {GRADER_LABELS_FIELD: (row_hash, serialize(LABELS))}}
        if row_hash
        else {}
    )
    mocker.patch(f"{API}.course_translations", return_value=rows)
    course = mocker.Mock(
        raw_grader=[{"type": t, "short_label": label} for t, label in GRADERS]
    )
    mocker.patch(f"{API}.modulestore").return_value.get_course.return_value = course

    assert grader_labels(COURSE_KEY) == expected


def _run(step, data, mocker, labels=LABELS):
    mocker.patch(f"{FILTERS}.grader_labels", return_value=labels)
    return step(filter_type="test", running_pipeline=[]).run_filter(
        course_key=COURSE_KEY, user=None, data=data
    )["data"]


def test_progress_assignment_types_translated_together(mocker):
    data = {
        "grading_policy": {
            "assignment_policies": [{"type": "Homework", "short_label": "HW"}]
        },
        "assignment_type_grade_summary": [{"type": "Exam", "short_label": "Ex"}],
        "section_scores": [
            {"subsections": [{"assignment_type": "Homework"}, {"assignment_type": ""}]}
        ],
    }

    result = _run(TranslateProgressAssignmentTypes, data, mocker)

    assert result["grading_policy"]["assignment_policies"] == [
        {"type": "Devoirs", "short_label": "DEV"}
    ]
    assert result["assignment_type_grade_summary"] == [
        {"type": "Examen", "short_label": "EX"}
    ]
    assert [
        s["assignment_type"] for s in result["section_scores"][0]["subsections"]
    ] == [
        "Devoirs",
        "",
    ]


def test_dates_assignment_types_translated(mocker):
    data = {
        "course_date_blocks": [{"assignment_type": "Exam"}, {"assignment_type": None}]
    }

    result = _run(TranslateDatesAssignmentTypes, data, mocker)

    assert [d["assignment_type"] for d in result["course_date_blocks"]] == [
        "Examen",
        None,
    ]


@pytest.mark.parametrize(
    ("step", "data", "blocks_path"),
    [
        (
            TranslateOutlineTabAssignmentTypes,
            {
                "course_blocks": {
                    "blocks": {
                        "a": {"description": "Homework"},
                        "b": {"description": "Timed exam"},
                    }
                },
                "dates_widget": {"course_date_blocks": [{"assignment_type": "Exam"}]},
            },
            ("course_blocks", "blocks"),
        ),
        (
            TranslateCourseNavigationAssignmentTypes,
            {
                "blocks": {
                    "a": {"description": "Homework"},
                    "b": {"description": "Timed exam"},
                }
            },
            ("blocks",),
        ),
    ],
    ids=["outline_tab", "navigation"],
)
def test_block_descriptions_translated_only_for_type_names(
    mocker, step, data, blocks_path
):
    result = _run(step, data, mocker)

    blocks = result
    for key in blocks_path:
        blocks = blocks[key]
    assert blocks == {
        "a": {"description": "Devoirs"},
        "b": {"description": "Timed exam"},
    }
    if "dates_widget" in result:
        assert result["dates_widget"]["course_date_blocks"] == [
            {"assignment_type": "Examen"}
        ]


def test_assignment_type_steps_leave_data_without_labels(mocker):
    data = {"course_date_blocks": [{"assignment_type": "Exam"}]}

    result = _run(TranslateDatesAssignmentTypes, data, mocker, labels={})

    assert result == {"course_date_blocks": [{"assignment_type": "Exam"}]}


def test_refresh_problem_feedback_keeps_feedback_for_another_result(mocker):
    mocker.patch(f"{API}.in_place_translations_enabled", return_value=True)
    responder = _responder(
        mocker, responsetypes.MultipleChoiceResponse, rebuilt_correctness="incorrect"
    )
    block = _problem(mocker, responder)

    refresh_problem_feedback(block)

    assert block.lcp.correct_map.get_msg("p_2_1") == "<p>Exact</p>"


@pytest.mark.django_db
def test_course_translations_serves_current_rows_for_the_language(mocker):
    from django.utils import translation  # noqa: PLC0415
    from edx_django_utils.cache import RequestCache  # noqa: PLC0415
    from ol_openedx_auto_select_language.translations import (  # noqa: PLC0415
        course_translations,
    )
    from ol_openedx_course_translations.models import BlockTranslation  # noqa: PLC0415

    usage = COURSE_KEY.make_usage_key("html", "a")
    for field, language, status in [
        ("display_name", "fr", BlockTranslation.Status.AUTO),
        ("data", "fr", BlockTranslation.Status.REVIEWED),
        ("title", "fr", BlockTranslation.Status.STALE),
        ("display_name", "es", BlockTranslation.Status.AUTO),
    ]:
        BlockTranslation.objects.create(
            course_key=COURSE_KEY,
            usage_key=usage,
            field=field,
            language=language,
            source_hash="h",
            translated_value=f"{field}-{language}",
            status=status,
        )
    enabled = mocker.patch(f"{API}.in_place_translations_enabled", return_value=True)

    with translation.override("fr"):
        # Loaded with only the name fields first, so a shared cache entry would
        # leave ``data`` out of the full load.
        assert set(course_translations(COURSE_KEY, ("display_name",))[usage]) == {
            "display_name"
        }
        assert set(course_translations(COURSE_KEY)[usage]) == {"display_name", "data"}
        assert usage in course_translations(COURSE_KEY, block_type="html")
        assert course_translations(COURSE_KEY, block_type="problem") == {}
    with translation.override("es"):
        assert course_translations(COURSE_KEY)[usage] == {
            "display_name": ("h", "display_name-es")
        }
    RequestCache.clear_all_namespaces()
    enabled.return_value = False
    with translation.override("fr"):
        assert course_translations(COURSE_KEY) == {}


def test_courseware_metadata_name_stays_escaped(mocker):
    course = COURSE_KEY.make_usage_key("course", "course")
    mocker.patch(
        f"{FILTERS}.course_translations",
        return_value={course: {"display_name": (source_hash("A & B"), "<b>X</b> & Y")}},
    )
    data = {"name": "A &amp; B"}

    TranslateCoursewareMetadata(filter_type="test", running_pipeline=[]).run_filter(
        course_key=COURSE_KEY, user=None, data=data
    )

    assert data["name"] == "&lt;b&gt;X&lt;/b&gt; &amp; Y"
