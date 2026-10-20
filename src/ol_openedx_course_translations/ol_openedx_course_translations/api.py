"""Read side of in-place course translations: which values a learner is served."""

import hashlib
import html
import json
import logging
import re

from crum import get_current_request
from django.conf import settings
from django.utils.translation import get_language, get_language_info
from edx_django_utils.cache import RequestCache
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.waffle_utils import CourseWaffleFlag

from ol_openedx_course_translations.blocks import (
    ANSWER_NOTE_FIELDS,
    SOURCE_TEXT_HANDLERS,
    TRANSLATABLE_BLOCK_FIELDS,
    TYPED_ANSWER_TAGS,
    deserialize,
    serialize,
)
from ol_openedx_course_translations.models import BlockTranslation

log = logging.getLogger(__name__)

# .. toggle_name: ol_openedx_course_translations.in_place_translations
# .. toggle_implementation: CourseWaffleFlag
# .. toggle_default: False
# .. toggle_description: Serve BlockTranslation rows in the learner's active
#   language for this course's content, titles and pages.
IN_PLACE_TRANSLATIONS = CourseWaffleFlag(
    "ol_openedx_course_translations.in_place_translations", __name__
)

SERVABLE_STATUSES = (
    BlockTranslation.Status.AUTO,
    BlockTranslation.Status.REVIEWED,
)

DEFAULT_ANSWER_LANGUAGE_NOTE = "Please enter your answers in {language}."
PROBLEM_OPEN_TAG = re.compile(r"<problem\b[^>]*>")


def source_hash(value):
    """Return the fingerprint a translation row is checked against."""
    return hashlib.sha256(serialize(value).encode()).hexdigest()


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

    Empty when the course flag is off. Loaded once per request, course and language.
    """
    language = get_language()
    course_key = plain_key(course_key)
    if not language or not IN_PLACE_TRANSLATIONS.is_enabled(course_key):
        return {}
    cache = RequestCache("ol_openedx_course_translations")
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
    dirty when read, so they are dropped from the dirty set. The block is bound
    to one learner for one request, so nothing carries over to another learner.

    A row whose ``source_hash`` no longer matches the live value was made from
    older source text, so the source value is kept instead.
    """
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
        elif ANSWER_NOTE_FIELDS.get(block_type) == name:
            value = add_prompt_answer_note(value, usage_key.course_key)
        field = block.fields[name]
        field._set_cached_value(block, value)  # noqa: SLF001
        block._dirty_fields.pop(field, None)  # noqa: SLF001


def answer_language_note(course_key):
    """Return the note telling learners which language answers are graded in."""
    notes = getattr(settings, "IN_PLACE_TRANSLATION_ANSWER_LANGUAGE_NOTES", {})
    text = notes.get(get_language(), DEFAULT_ANSWER_LANGUAGE_NOTE)
    note = text.replace("{language}", course_language_name(course_key))
    return f'<p class="ol-answer-language-note">{html.escape(note)}</p>'


def add_problem_answer_note(problem_xml, course_key):
    """Add the note to problems whose answers are typed or picked as text."""
    if not any(f"<{tag}" in problem_xml for tag in TYPED_ANSWER_TAGS):
        return problem_xml
    match = PROBLEM_OPEN_TAG.search(problem_xml)
    if not match:
        return problem_xml
    note = answer_language_note(course_key)
    return problem_xml[: match.end()] + note + problem_xml[match.end() :]


def add_prompt_answer_note(prompt, course_key):
    """Add the note to an ORA prompt, which is HTML or a JSON list of prompts."""
    note = answer_language_note(course_key)
    try:
        prompts = json.loads(prompt)
    except (TypeError, ValueError):
        return note + prompt
    if isinstance(prompts, list) and prompts and isinstance(prompts[0], dict):
        prompts[0]["description"] = note + (prompts[0].get("description") or "")
        return json.dumps(prompts)
    return note + prompt
