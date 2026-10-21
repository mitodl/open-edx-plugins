"""Show BlockTranslation rows to learners: which values a learner is served."""

import html
import logging
import re

from crum import get_current_request
from django.conf import settings
from django.utils.translation import get_language, get_language_info
from edx_django_utils.cache import RequestCache
from ol_openedx_course_translations.blocks import (
    SOURCE_TEXT_HANDLERS,
    TRANSLATABLE_BLOCK_FIELDS,
    TYPED_ANSWER_TAGS,
    deserialize,
    source_hash,
)
from ol_openedx_course_translations.models import BlockTranslation
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview

from ol_openedx_auto_select_language.toggles import in_place_translations_enabled

try:
    from xblocks_contrib.problem.capa import responsetypes
    from xblocks_contrib.problem.capa.util import convert_files_to_filenames
except ImportError:  # Releases before the problem block moved to xblocks-contrib.
    from xmodule.capa import responsetypes
    from xmodule.capa.util import convert_files_to_filenames

log = logging.getLogger(__name__)

# Responses whose feedback comes only from the problem XML, so grading them again
# runs no course code and calls no external grader.
FEEDBACK_REBUILD_RESPONSES = (
    responsetypes.ChoiceResponse,
    responsetypes.MultipleChoiceResponse,
    responsetypes.NumericalResponse,
    responsetypes.OptionResponse,
    responsetypes.StringResponse,
)
FEEDBACK_PROPERTIES = ("msg", "hint", "hintmode")

# Source values of the fields translate_block replaced on a block instance.
ORIGINAL_VALUES_ATTR = "_ol_translation_original_values"

SERVABLE_STATUSES = (
    BlockTranslation.Status.AUTO,
    BlockTranslation.Status.REVIEWED,
)

DEFAULT_ANSWER_LANGUAGE_NOTE = "Please enter your answers in {language}."
ANSWER_LANGUAGE_NOTE_HTML = (
    '<div class="ol-answer-language-note" role="note" style="display: flex; '
    "gap: 10px; align-items: flex-start; margin: 0 0 16px; padding: 10px 14px; "
    "border-left: 4px solid #b45309; border-radius: 4px; background: #fff7ed; "
    'color: #7c2d12; font-size: 14px; line-height: 1.4;">'
    '<span aria-hidden="true" style="font-size: 16px; line-height: 1.2;">&#9888;</span>'
    "<span>{note}</span></div>"
)
PROBLEM_OPEN_TAG = re.compile(r"<problem\b[^>]*>")


def plain_key(key):
    """Drop branch and version from a key, so it matches the stored published keys."""
    if hasattr(key, "for_branch"):
        key = key.for_branch(None)
    if hasattr(key, "version_agnostic"):
        key = key.version_agnostic()
    return key


def course_translations(course_key):
    """
    Return ``{usage_key: {field: (source_hash, value)}}`` for the learner's language.

    Empty when the course is not in in-place translations mode. Loaded once per
    request, course and language.
    """
    language = get_language()
    course_key = plain_key(course_key)
    if not language or not in_place_translations_enabled(course_key):
        return {}
    cache = RequestCache("ol_openedx_auto_select_language.translations")
    cache_key = f"{course_key}:{language}"
    cached = cache.get_cached_response(cache_key)
    if cached.is_found:
        return cached.value
    translations = {}
    rows = BlockTranslation.objects.filter(
        course_key=course_key, language=language, status__in=SERVABLE_STATUSES
    ).values_list("usage_key", "field", "source_hash", "translated_value")
    for usage_key, field, row_hash, value in rows:
        translations.setdefault(usage_key, {})[field] = (row_hash, value)
    cache.set(cache_key, translations)
    return translations


def course_language_codes(course_key):
    """Return the codes a course can be shown in: its own language and translations."""
    course_key = plain_key(course_key)
    codes = set(
        BlockTranslation.objects.filter(
            course_key=course_key, status__in=SERVABLE_STATUSES
        )
        .values_list("language", flat=True)
        .distinct()
    )
    try:
        own_language = CourseOverview.get_from_id(course_key).language
    except CourseOverview.DoesNotExist:
        own_language = None
    codes.add((own_language or settings.LANGUAGE_CODE).replace("_", "-").lower())
    return codes


def translated_text(translations, usage_key, field, source_value):
    """Return the translation of a text value, or the source when none is current."""
    row_hash, value = translations.get(usage_key, {}).get(field, (None, None))
    if row_hash is None or row_hash != source_hash(source_value):
        return source_value
    return value


def course_language_name(course_key):
    """Return the course language's own name, for the answer-language note."""
    language = CourseOverview.get_from_id(course_key).language or settings.LANGUAGE_CODE
    try:
        return get_language_info(language.replace("_", "-").lower())["name_local"]
    except KeyError:
        return language


def handler_needs_source_text(block):
    """Return True when the current request runs a handler that must see the source."""
    handlers = SOURCE_TEXT_HANDLERS.get(block.scope_ids.block_type)
    request = get_current_request()
    match = getattr(request, "resolver_match", None) if request else None
    return bool(handlers and match and match.kwargs.get("handler") in handlers)


def translate_block(block):
    """
    Put translated values into the block's in-memory field cache.

    Writing the field normally would mark it dirty, and a later ``save()`` would
    raise ``InvalidScopeError`` because the LMS keeps authored scopes read-only.
    Seeding the cache is not saved; mutable (List/Dict) fields are also marked
    dirty when read, so they are dropped from the dirty set.

    The same instance can be bound again in a request, to another user (for
    example rescoring) or for a handler that needs the source text, so the
    source values are put back before anything is applied.

    A row whose ``source_hash`` no longer matches the live value was made from
    older source text, so the source value is kept instead.
    """
    originals = block.__dict__.setdefault(ORIGINAL_VALUES_ATTR, {})
    for name, original in originals.items():
        _set_in_memory(block, name, original)
    originals.clear()
    usage_key = plain_key(block.scope_ids.usage_id)
    block_type = block.scope_ids.block_type
    fields = TRANSLATABLE_BLOCK_FIELDS.get(block_type)
    if not fields or handler_needs_source_text(block):
        return
    rows = course_translations(usage_key.course_key).get(usage_key)
    if not rows:
        return
    for name in fields:
        row_hash, value = rows.get(name, (None, None))
        source_value = getattr(block, name, None)
        if row_hash is None or row_hash != source_hash(source_value):
            continue
        try:
            value = deserialize(source_value, value)
        except ValueError:
            log.exception("Invalid BlockTranslation %s %s", usage_key, name)
            continue
        if block_type == "problem" and name == "data":
            value = add_problem_answer_note(value, usage_key.course_key)
        originals[name] = source_value
        _set_in_memory(block, name, value)


def refresh_problem_feedback(block):
    """
    Rebuild a problem's saved feedback in the active language, in memory.

    When a learner submits, the problem saves its feedback (choice hints and
    labels such as "Correct:") in their state, in the language active then, and
    shows it as saved on later visits. The feedback is rebuilt from the problem
    text now being shown; the saved correctness and score are kept.

    The block drops its problem every time it is bound, also again to the same
    user (when this filter step does not run), and builds it again from the saved
    state, so the rebuilt feedback is also put in the state, in memory only.
    """
    if block.scope_ids.block_type != "problem" or not block.correct_map:
        return
    if not in_place_translations_enabled(
        plain_key(block.scope_ids.usage_id).course_key
    ):
        return
    lcp = block.lcp
    answers = convert_files_to_filenames(lcp.student_answers)
    for responder in lcp.responders.values():
        hintgroup = responder.xml.find("hintgroup")
        if not isinstance(responder, FEEDBACK_REBUILD_RESPONSES) or (
            hintgroup is not None and hintgroup.get("hintfn")
        ):
            continue
        answer_ids = [aid for aid in responder.answer_ids if aid in lcp.correct_map]
        if not answer_ids:
            continue
        try:
            rebuilt = responder.evaluate_answers(answers, lcp.correct_map)
        except Exception:  # noqa: BLE001 - keep the saved feedback if it cannot be rebuilt
            log.warning("Could not rebuild feedback for %s", block.scope_ids.usage_id)
            continue
        for aid in answer_ids:
            if aid not in rebuilt:
                continue
            for name in FEEDBACK_PROPERTIES:
                lcp.correct_map.set_property(aid, name, rebuilt.get_property(aid, name))
    _set_in_memory(block, "correct_map", lcp.correct_map.get_dict())


def _set_in_memory(block, name, value):
    """Set a field's cached value without marking it for saving."""
    field = block.fields[name]
    field._set_cached_value(block, value)  # noqa: SLF001
    block._dirty_fields.pop(field, None)  # noqa: SLF001


def answer_language_note(course_key):
    """Return the note telling learners which language answers are graded in."""
    notes = getattr(settings, "IN_PLACE_TRANSLATION_ANSWER_LANGUAGE_NOTES", {})
    text = notes.get(get_language(), DEFAULT_ANSWER_LANGUAGE_NOTE)
    note = text.replace("{language}", course_language_name(course_key))
    # Inline styles: the note renders in problem and ORA markup, outside any theme.
    return ANSWER_LANGUAGE_NOTE_HTML.format(note=html.escape(note))


def add_problem_answer_note(problem_xml, course_key):
    """Add the note to problems whose answers are typed or picked as text."""
    if not any(f"<{tag}" in problem_xml for tag in TYPED_ANSWER_TAGS):
        return problem_xml
    match = PROBLEM_OPEN_TAG.search(problem_xml)
    if not match:
        return problem_xml
    note = answer_language_note(course_key)
    return problem_xml[: match.end()] + note + problem_xml[match.end() :]
