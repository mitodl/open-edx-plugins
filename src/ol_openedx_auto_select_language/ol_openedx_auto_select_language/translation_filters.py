"""Open edX filter steps that show course content in the learner's language."""

import html
import re

from ol_openedx_course_translations.blocks import ANSWER_NOTE_BLOCK_TYPES, source_hash
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import UsageKey
from openedx_filters import PipelineStep

from ol_openedx_auto_select_language.translations import (
    NAME_FIELDS,
    answer_language_note,
    course_translations,
    grader_labels,
    plain_key,
    refresh_problem_feedback,
    translate_block,
    translated_text,
)

STATIC_TAB_ID_PREFIX = "static_tab_"
BLOCK_TITLE = re.compile(r'<h3 class="openassessment__title[^"]*">.*?</h3>', re.DOTALL)


def _usage_key(value):
    try:
        return UsageKey.from_string(value)
    except InvalidKeyError:
        return None


def _course_usage_key(course_key):
    return course_key.make_usage_key("course", "course")


class TranslateBoundBlock(PipelineStep):
    """
    Translate a block as soon as it is bound to a learner.

    Every learner-facing load goes through the bind: unit children, library and
    conditional children, handler calls (problem Submit), sequence metadata (unit
    titles), static tabs, handouts, updates and about sections.
    """

    def run_filter(self, block, user, course_key):
        """Swap the block's authored text for the learner's language."""
        translate_block(block)
        refresh_problem_feedback(block)
        return {"block": block, "user": user, "course_key": course_key}


class TranslateCourseOutline(PipelineStep):
    """Translate titles in the learning sequences outline (breadcrumbs, next up)."""

    def run_filter(self, course_key, user, data):
        """Translate the course, section and subsection titles."""
        translations = course_translations(course_key, NAME_FIELDS)
        if translations:
            data["title"] = translated_text(
                translations,
                _course_usage_key(course_key),
                "display_name",
                data["title"],
            )
            outline = data.get("outline", {})
            items = [
                *outline.get("sections", []),
                *outline.get("sequences", {}).values(),
            ]
            for item in items:
                usage_key = _usage_key(item.get("id", ""))
                if usage_key:
                    item["title"] = translated_text(
                        translations, usage_key, "display_name", item.get("title")
                    )
        return {"course_key": course_key, "user": user, "data": data}


class TranslateCourseHomeMetadata(PipelineStep):
    """Translate the course title and static tab names in the course header."""

    def run_filter(self, course_key, user, data):
        """Translate the title and the names of static tabs."""
        translations = course_translations(course_key, NAME_FIELDS)
        if translations:
            data["title"] = translated_text(
                translations,
                _course_usage_key(course_key),
                "display_name",
                data["title"],
            )
            for tab in data.get("tabs", []):
                tab_id = tab.get("tab_id", "")
                if tab_id.startswith(STATIC_TAB_ID_PREFIX):
                    usage_key = course_key.make_usage_key(
                        "static_tab", tab_id.removeprefix(STATIC_TAB_ID_PREFIX)
                    )
                    tab["title"] = translated_text(
                        translations, usage_key, "display_name", tab.get("title")
                    )
        return {"course_key": course_key, "user": user, "data": data}


class TranslateCoursewareMetadata(PipelineStep):
    """Translate the course name in the courseware metadata."""

    def run_filter(self, course_key, user, data):
        """Translate the (HTML-escaped) course name."""
        translations = course_translations(course_key, NAME_FIELDS)
        if translations and data.get("name"):
            name = html.unescape(data["name"])
            data["name"] = html.escape(
                translated_text(
                    translations, _course_usage_key(course_key), "display_name", name
                )
            )
        return {"course_key": course_key, "user": user, "data": data}


def _translate_assignment_types(labels, entries, key="assignment_type"):
    """
    Translate ``entry[key]`` where it is a grading type name.

    Block descriptions of special exams hold the exam's own text, which is kept.
    """
    for entry in entries:
        if entry.get(key) in labels:
            entry[key] = labels[entry[key]]["type"]


def _translate_names(names, entries, key, *, with_suffix=False):
    """
    Translate ``entry[key]`` where it is a block name with a current translation.

    These responses name blocks without always giving their ids, so names are
    matched by source text: a translation row is current exactly when its source
    hash is the hash of the name shown. With ``with_suffix``, a name followed by
    " (...)" that the platform adds has the name part translated: the step of
    an ORA date ("<ORA title> (<step>)") or a graded subsection's question
    count ("<name> (<n> Questions)"). The suffix is already in the learner's
    language.
    """
    for entry in entries:
        name = entry.get(key)
        if not name:
            continue
        if (translated := names.get(source_hash(name))) is not None:
            entry[key] = translated
        elif with_suffix:
            block_name, sep, suffix = name.rpartition(" (")
            if sep and (translated := names.get(source_hash(block_name))) is not None:
                entry[key] = f"{translated}{sep}{suffix}"


class _CourseHomeNamesStep(PipelineStep):
    """
    Translate block and grading type names in a course home API response.

    The response is built per request after any cache, so the shared course
    data the platform caches and grades from keeps the source names.
    """

    def run_filter(self, course_key, user, data):
        """Swap the names for the learner's language, where translated."""
        translations = course_translations(course_key, NAME_FIELDS)
        if translations:
            # ORA dates show the ORA's title, which can differ from its name.
            names = dict(
                fields[field]
                for fields in translations.values()
                for field in ("display_name", "title")
                if field in fields
            )
            self.translate(names, grader_labels(course_key), data)
        return {"course_key": course_key, "user": user, "data": data}

    def translate(self, names, labels, data):
        """Translate the response's names in place."""
        raise NotImplementedError


class TranslateProgress(_CourseHomeNamesStep):
    """
    Translate section, subsection and grading type names on the progress tab.

    The grading policy, the grade summary and the subsections' types are translated
    together: the progress page compares them by name.
    """

    def translate(self, names, labels, data):
        """Swap each name and short label for its translation."""
        policies = (data.get("grading_policy") or {}).get("assignment_policies", [])
        for entry in [*policies, *data.get("assignment_type_grade_summary", [])]:
            label = labels.get(entry.get("type"))
            if label:
                entry["type"] = label["type"]
                if entry.get("short_label") and label["short_label"]:
                    entry["short_label"] = label["short_label"]
        sections = data.get("section_scores", [])
        _translate_names(names, sections, "display_name")
        for section in sections:
            subsections = section.get("subsections", [])
            _translate_names(names, subsections, "display_name")
            _translate_assignment_types(labels, subsections)


def _translate_dates(names, labels, dates):
    _translate_names(names, dates, "title", with_suffix=True)
    _translate_assignment_types(labels, dates)


class TranslateDates(_CourseHomeNamesStep):
    """Translate assignment titles and grading type names on the dates tab."""

    def translate(self, names, labels, data):
        """Swap each date's title and grading type name for its translation."""
        _translate_dates(names, labels, data.get("course_date_blocks", []))


class TranslateOutlineTab(_CourseHomeNamesStep):
    """Translate the course outline tab: block names, types and its dates widget."""

    def translate(self, names, labels, data):
        """Swap block names, subsection descriptions and dates."""
        blocks = (data.get("course_blocks") or {}).get("blocks", {}).values()
        _translate_names(names, blocks, "display_name", with_suffix=True)
        _translate_assignment_types(labels, blocks, key="description")
        dates = (data.get("dates_widget") or {}).get("course_date_blocks", [])
        _translate_dates(names, labels, dates)


class TranslateCourseNavigation(_CourseHomeNamesStep):
    """Translate block names and types in the courseware navigation sidebar."""

    def translate(self, names, labels, data):
        """Swap block names and subsection descriptions for their translations."""
        blocks = data.get("blocks", {}).values()
        _translate_names(names, blocks, "display_name", with_suffix=True)
        _translate_assignment_types(labels, blocks, key="description")


class AddAnswerNoteBelowTitles(PipelineStep):
    """
    Put the answer-language note right below the title of translated ORA blocks.

    Their prompt sits inside a collapsible step, where a note in the prompt is
    easy to miss, and their title is plain text, so the note is added to the
    unit's rendered HTML instead.
    """

    def run_filter(self, block, fragment, context, view):
        """Insert the note after each translated ORA title in the unit."""
        course_key = block.scope_ids.usage_id.course_key
        content = fragment.content
        for child_key in getattr(block, "children", []):
            if child_key.block_type in ANSWER_NOTE_BLOCK_TYPES and (
                course_translations(course_key, block_type=child_key.block_type).get(
                    plain_key(child_key)
                )
            ):
                content = _insert_after_title(
                    content, str(child_key), answer_language_note(course_key)
                )
        fragment.content = content
        return {"block": block, "fragment": fragment, "context": context, "view": view}


def _insert_after_title(content, usage_id, note):
    """Insert ``note`` after the title of the child rendered with ``usage_id``."""
    start = content.find(f'data-id="{usage_id}"')
    match = BLOCK_TITLE.search(content, start) if start != -1 else None
    if not match:
        return content
    return content[: match.end()] + note + content[match.end() :]
