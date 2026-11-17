"""Check that a translated problem grades the same way as its source."""

import logging
from importlib import import_module

from django.conf import settings
from django.template.loader import render_to_string
from xmodule.contentstore.django import contentstore
from xmodule.util.sandboxing import SandboxService

log = logging.getLogger(__name__)


def capa_module(name):
    """
    Import ``name`` from the capa package of the problem block the platform runs.

    Releases with both packages pick the block with USE_EXTRACTED_PROBLEM_BLOCK;
    releases before the extraction only have ``xmodule.capa``.
    """
    packages = ["xblocks_contrib.problem.capa", "xmodule.capa"]
    if not getattr(settings, "USE_EXTRACTED_PROBLEM_BLOCK", True):
        packages.reverse()
    try:
        return import_module(f"{packages[0]}.{name}")
    except ImportError:
        return import_module(f"{packages[1]}.{name}")


capa_problem = capa_module("capa_problem")
LoncapaProblem, LoncapaSystem = capa_problem.LoncapaProblem, capa_problem.LoncapaSystem

# The field the LMS grades from.
GRADED_FIELD = ("problem", "data")
# Both versions are built with the same seed, so randomised values match.
SEED = 1


def _correct_answers(block, problem_xml):
    """Build the problem from ``problem_xml``; return it and its correct answers."""
    sandbox = SandboxService(
        contentstore=contentstore, course_id=block.location.course_key
    )
    system = LoncapaSystem(
        ajax_url=None,
        anonymous_student_id=None,
        cache=None,
        can_execute_unsafe_code=sandbox.can_execute_unsafe_code,
        get_python_lib_zip=sandbox.get_python_lib_zip,
        DEBUG=False,
        i18n=block.runtime.service(block, "i18n"),
        render_template=render_to_string,
        resources_fs=block.runtime.resources_fs,
        seed=SEED,
        xqueue=None,
        matlab_api_key=None,
    )
    lcp = LoncapaProblem(
        problem_text=problem_xml,
        id=block.location.html_id(),
        capa_system=system,
        capa_block=block,
        state={},
        seed=SEED,
    )
    answers = {
        answer_id: answer
        for answer_id, answer in lcp.get_question_answers().items()
        if answer_id in lcp.inputs
    }
    return lcp, answers


def _grades(lcp, answers):
    """Return how each answer is graded."""
    graded = lcp.grade_answers(answers)
    return {answer_id: graded.get_correctness(answer_id) for answer_id in answers}


def grades_like_source(block, translated_xml):
    """
    Return True when the translation's correct answers are the source's and grade alike.

    Graded parts are copied back from the source before this runs, so a
    difference means the copy missed something the grader reads. A problem
    that cannot be built (a script that fails without a sandbox) cannot be
    checked, and counts as a difference. Some response types list correct
    answers that are not submissions (image regions, schematics, annotations);
    when the source cannot grade its own, only the answers are compared.
    """
    try:
        source, source_answers = _correct_answers(block, block.data)
        translated, translated_answers = _correct_answers(block, translated_xml)
    except Exception:  # a problem that cannot be built cannot be checked
        log.warning(
            "Could not build %s to compare grading", block.location, exc_info=True
        )
        return False
    if source_answers != translated_answers:
        return False
    try:
        source_grades = _grades(source, source_answers)
    except Exception:  # noqa: BLE001 - its answers are not submissions; they matched
        return True
    try:
        return source_grades == _grades(translated, translated_answers)
    except Exception:  # the source grades these answers, so the translation must too
        log.warning("Could not grade translated %s", block.location, exc_info=True)
        return False
