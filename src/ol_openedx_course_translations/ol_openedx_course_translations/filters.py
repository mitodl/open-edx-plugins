"""Open edX filter steps that show course content in the learner's language."""

from django.utils.translation import get_language
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx_filters import PipelineStep

from ol_openedx_course_translations.api import (
    IN_PLACE_TRANSLATIONS,
    LIBRARY_BLOCK_TYPES,
    apply_translations,
    get_translations,
)


def translate_block(block):
    """
    Swap the block's authored text for the learner's language, in memory only.

    A library block renders its children itself, so they never reach the
    vertical child filter; they are translated here instead. ``get_children()``
    is used rather than the learner's selection because selecting saves user
    state and emits analytics events. It returns the same instances the
    library block renders a moment later, through split's per-request cache.
    """
    course_key = block.scope_ids.usage_id.course_key
    if not IN_PLACE_TRANSLATIONS.is_enabled(course_key):
        return
    blocks = [block]
    if block.scope_ids.block_type in LIBRARY_BLOCK_TYPES:
        blocks += block.get_children()
    translations = get_translations(
        [item.scope_ids.usage_id for item in blocks], get_language()
    )
    if not translations:
        return
    course_language = CourseOverview.get_from_id(course_key).language
    for item in blocks:
        item_translations = translations.get(item.scope_ids.usage_id)
        if item_translations:
            apply_translations(item, item_translations, course_language)


class TranslateVerticalChildContent(PipelineStep):
    """Translate a unit child before it renders."""

    def run_filter(self, block, context):
        """Translate the child, and a library block's children."""
        translate_block(block)
        return {"block": block, "context": context}


class TranslateBlockBeforeHandler(PipelineStep):
    """
    Translate a block before one of its handlers runs.

    Problem Submit, Reset and Show Answer reload the block in a new request
    and re-render it from ``data``, so without this the problem would switch
    back to the source language after the learner's first click.
    """

    def run_filter(self, block, handler):
        """Translate the block the handler is about to use."""
        translate_block(block)
        return {"block": block, "handler": handler}
