"""Open edX filter steps that show course content in the learner's language."""

import html

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import UsageKey
from openedx_filters import PipelineStep

from ol_openedx_course_translations.api import (
    course_translations,
    translate_block,
    translated_text,
)

STATIC_TAB_ID_PREFIX = "static_tab_"


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
        return {"block": block, "user": user, "course_key": course_key}


class TranslateCourseBlockNames(PipelineStep):
    """
    Translate block names in a learner's transformed course block structure.

    Covers the course outline, navigation sidebar, blocks API, dates and progress
    section names. The structure is a per-request copy, so the shared block
    structure cache is not changed.
    """

    def run_filter(self, block_structure, user, starting_block_usage_key):
        """Override ``display_name`` with its translation where one is current."""
        translations = course_translations(starting_block_usage_key.course_key)
        if translations:
            for usage_key in block_structure:
                name = block_structure.get_xblock_field(usage_key, "display_name")
                translated = translated_text(
                    translations, usage_key, "display_name", name
                )
                if translated != name:
                    block_structure.override_xblock_field(
                        usage_key, "display_name", translated
                    )
        return {
            "block_structure": block_structure,
            "user": user,
            "starting_block_usage_key": starting_block_usage_key,
        }


class TranslateCourseOutline(PipelineStep):
    """Translate titles in the learning sequences outline (breadcrumbs, next up)."""

    def run_filter(self, course_key, user, data):
        """Translate the course, section and subsection titles."""
        translations = course_translations(course_key)
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
        translations = course_translations(course_key)
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
        translations = course_translations(course_key)
        if translations and data.get("name"):
            name = html.unescape(data["name"])
            data["name"] = html.escape(
                translated_text(
                    translations, _course_usage_key(course_key), "display_name", name
                )
            )
        return {"course_key": course_key, "user": user, "data": data}
