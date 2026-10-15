"""Read side of in-place course translations: which values a learner is served."""

import hashlib
import html
import re

from django.conf import settings
from django.utils.translation import get_language, get_language_info
from lxml import etree
from openedx.core.djangoapps.waffle_utils import CourseWaffleFlag

from ol_openedx_course_translations.models import BlockTranslation

# .. toggle_name: ol_openedx_course_translations.in_place_translations
# .. toggle_implementation: CourseWaffleFlag
# .. toggle_default: False
# .. toggle_description: Serve BlockTranslation rows in the learner's active
#   language inside course units, instead of the course's own content.
IN_PLACE_TRANSLATIONS = CourseWaffleFlag(
    "ol_openedx_course_translations.in_place_translations", __name__
)

TRANSLATABLE_BLOCK_FIELDS = {
    "html": ("data", "display_name"),
    "problem": ("data", "display_name"),
    "video": ("display_name",),
}

# Parents that render their children themselves, so the vertical child filter
# never sees those children.
LIBRARY_BLOCK_TYPES = ("library_content", "itembank")

SERVABLE_STATUSES = (
    BlockTranslation.Status.AUTO,
    BlockTranslation.Status.REVIEWED,
)

# Capa grades against these, and stores dropdown answers as the option text,
# so they must stay in the course language whatever the learner reads.
GRADED_ATTRIBUTES = ("answer", "options", "correct")
GRADED_TEXT_TAGS = ("script", "answer", "grader_payload", "option")
TYPED_ANSWER_TAGS = ("stringresponse", "optionresponse")

DEFAULT_ANSWER_LANGUAGE_NOTE = "Please enter your answers in {language}."
PROBLEM_OPEN_TAG = re.compile(r"<problem\b[^>]*>")


def source_hash(value):
    """Return the fingerprint a translation row is checked against."""
    return hashlib.sha256((value or "").encode()).hexdigest()


def get_translations(usage_keys, language):
    """Return ``{usage_key: {field: (source_hash, value)}}`` in one query."""
    if not usage_keys or not language:
        return {}
    rows = BlockTranslation.objects.filter(
        usage_key__in=usage_keys,
        language=language,
        status__in=SERVABLE_STATUSES,
    ).values_list("usage_key", "field", "source_hash", "translated_value")
    translations = {}
    for usage_key, field, row_hash, value in rows:
        translations.setdefault(usage_key, {})[field] = (row_hash, value)
    return translations


def apply_translations(block, translations, answer_language):
    """
    Put translated values into the block's in-memory field cache.

    Writing the field normally would mark it dirty, and the ``save()`` the
    runtime runs after render would then raise ``InvalidScopeError`` because
    the LMS keeps authored scopes read-only. Seeding the cache is never saved.
    The block instance is built for this request and this learner, so nothing
    carries over to another learner.

    A row whose ``source_hash`` no longer matches the live value was made from
    older source text, so the source value is kept instead.
    """
    block_type = block.scope_ids.block_type
    for name in TRANSLATABLE_BLOCK_FIELDS.get(block_type, ()):
        row_hash, value = translations.get(name, (None, None))
        if row_hash is None or row_hash != source_hash(getattr(block, name)):
            continue
        if block_type == "problem" and name == "data":
            value = add_answer_language_note(value, answer_language)
        block.fields[name]._set_cached_value(block, value)  # noqa: SLF001


def add_answer_language_note(problem_xml, answer_language):
    """Tell the learner which language typed and dropdown answers are graded in."""
    if not answer_language or not any(
        f"<{tag}" in problem_xml for tag in TYPED_ANSWER_TAGS
    ):
        return problem_xml
    match = PROBLEM_OPEN_TAG.search(problem_xml)
    if not match:
        return problem_xml
    try:
        language_name = get_language_info(answer_language)["name_local"]
    except KeyError:
        language_name = answer_language
    notes = getattr(settings, "IN_PLACE_TRANSLATION_ANSWER_LANGUAGE_NOTES", {})
    note = notes.get(get_language(), DEFAULT_ANSWER_LANGUAGE_NOTE).format(
        language=language_name
    )
    paragraph = f'<p class="ol-answer-language-note">{html.escape(note)}</p>'
    return problem_xml[: match.end()] + paragraph + problem_xml[match.end() :]


def restore_graded_parts(source_xml, translated_xml):
    """
    Return the translated problem XML with every graded part copied from source.

    Returns ``None`` when the two documents do not have the same element
    structure, because then parts cannot be matched up safely.
    """
    try:
        source = etree.fromstring(source_xml)
        translated = etree.fromstring(translated_xml)
    except (etree.XMLSyntaxError, ValueError):
        return None
    source_nodes = list(source.iter())
    translated_nodes = list(translated.iter())
    if [node.tag for node in source_nodes] != [node.tag for node in translated_nodes]:
        return None
    for source_node, translated_node in zip(source_nodes, translated_nodes):
        for attribute in GRADED_ATTRIBUTES:
            if attribute in source_node.attrib:
                translated_node.set(attribute, source_node.get(attribute))
        if source_node.tag in GRADED_TEXT_TAGS:
            translated_node.text = source_node.text
    return etree.tostring(translated, encoding="unicode")
