"""
Translate a course's published blocks straight into BlockTranslation rows.

No translated copy of the course is made: every field listed in
``TRANSLATABLE_BLOCK_FIELDS`` is read from the modulestore, translated with an
LLM provider, has its answers, grading code, ids and keys copied back from the
source, and is stored as an ``auto`` row. Fields that already have a current
row (same source text) or a reviewed row are skipped, so running it again only
translates what changed.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from ol_openedx_course_translations.blocks import (
    TRANSLATABLE_BLOCK_FIELDS,
    restore_kept_parts,
    serialize,
    source_hash,
)
from ol_openedx_course_translations.management.commands.backfill_block_translations import (  # noqa: E501
    save_rows,
)
from ol_openedx_course_translations.models import BlockTranslation
from ol_openedx_course_translations.utils.course_translations import (
    get_translation_provider,
    looks_like_markup,
    parse_and_validate_provider_spec,
)

# Fields holding XML rather than HTML, for the provider's DOM-aware path.
XML_FIELDS = {("problem", "data"), ("annotatable", "data")}


def _leaf_strings(value, found):
    """Collect every non-empty string in a JSON-like value, in order."""
    if isinstance(value, str):
        if value.strip():
            found.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            _leaf_strings(item, found)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _leaf_strings(item, found)
    return found


def _replace_leaf_strings(value, translations):
    """Rebuild a JSON-like value, taking strings from ``translations`` in order."""
    if isinstance(value, str):
        return next(translations) if value.strip() else value
    if isinstance(value, dict):
        return {
            key: _replace_leaf_strings(item, translations)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_replace_leaf_strings(item, translations) for item in value]
    return value


def translate_value(provider, block_type, field, source_value, language):
    """
    Return the field value translated, before kept parts are restored.

    Markup and plain text go through the provider's ``translate_text``; nested
    fields have their strings translated in one batch. Ids and keys among those
    strings are translated too, and put back by ``restore_kept_parts``.
    """
    if isinstance(source_value, str):
        tag_handling = None
        if looks_like_markup(source_value):
            tag_handling = "xml" if (block_type, field) in XML_FIELDS else "html"
        return provider.translate_text(
            source_value, language, tag_handling=tag_handling
        )
    strings = _leaf_strings(source_value, [])
    if not strings:
        return source_value
    plain = [string for string in strings if not looks_like_markup(string)]
    # The provider's batch API translates plain strings by id in one request;
    # strings holding markup go through the markup-aware path one by one.
    translated_plain = iter(
        provider._batch_translate_units(plain, language, None) if plain else []  # noqa: SLF001
    )
    translated = [
        provider.translate_text(string, language, tag_handling="html")
        if looks_like_markup(string)
        else next(translated_plain)
        for string in strings
    ]
    return _replace_leaf_strings(source_value, iter(translated))


def parse_course_and_language(options):
    """Return the course key and LMS language code, or raise CommandError."""
    try:
        course_key = CourseKey.from_string(options["course"])
    except InvalidKeyError as error:
        raise CommandError(str(error)) from error
    language = options["language"].lower().replace("_", "-")
    if language not in dict(settings.LANGUAGES):
        msg = f"--language must be a code from settings.LANGUAGES, got {language}."
        raise CommandError(msg)
    return course_key, language


def translated_row(provider, block, field, language):
    """Return an unsaved row for the field, or None when it could not be translated."""
    block_type = block.location.block_type
    source_value = getattr(block, field)
    translated = translate_value(provider, block_type, field, source_value, language)
    restored = restore_kept_parts(
        block_type, field, source_value, serialize(translated)
    )
    if restored is None or restored == source_value:
        return None
    return BlockTranslation(
        course_key=block.location.course_key,
        usage_key=block.location,
        field=field,
        language=language,
        source_hash=source_hash(source_value),
        translated_value=serialize(restored),
        status=BlockTranslation.Status.AUTO,
    )


class Command(BaseCommand):
    """Translate a course's blocks into BlockTranslation rows with an LLM."""

    help = __doc__

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument("--course", required=True, help="Course id to translate")
        parser.add_argument(
            "--language", required=True, help="Target language, e.g. fr or es-419"
        )
        parser.add_argument(
            "--provider",
            required=True,
            help="Translation provider, e.g. openai or openai/gpt-5.6",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-translate fields that already have a current auto row",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Translate every translatable field that has no current row."""
        # xmodule exists only inside edx-platform.
        from xmodule.modulestore import ModuleStoreEnum  # noqa: PLC0415
        from xmodule.modulestore.django import modulestore  # noqa: PLC0415

        course_key, language = parse_course_and_language(options)
        store = modulestore()
        if not store.has_course(course_key):
            msg = f"Course {course_key} does not exist."
            raise CommandError(msg)
        provider_name, model_name = parse_and_validate_provider_spec(
            options["provider"]
        )
        provider = get_translation_provider(provider_name, model_name)

        existing = {
            (usage_key, field): (row_hash, status)
            for usage_key, field, row_hash, status in BlockTranslation.objects.filter(
                course_key=course_key, language=language
            ).values_list("usage_key", "field", "source_hash", "status")
        }
        rows, skipped, failed = [], 0, []
        published = ModuleStoreEnum.RevisionOption.published_only
        for block_type, fields in TRANSLATABLE_BLOCK_FIELDS.items():
            for block in store.get_items(
                course_key, qualifiers={"category": block_type}, revision=published
            ):
                for field in fields:
                    source_value = getattr(block, field, None)
                    if not source_value:
                        continue
                    row_hash, status = existing.get(
                        (block.location, field), (None, None)
                    )
                    current = (
                        status == BlockTranslation.Status.AUTO
                        and row_hash == source_hash(source_value)
                    )
                    if status == BlockTranslation.Status.REVIEWED or (
                        current and not options["force"]
                    ):
                        skipped += 1
                        continue
                    row = translated_row(provider, block, field, language)
                    if row is None:
                        failed.append(f"{block.location} {field}")
                    else:
                        rows.append(row)
                        self.stdout.write(f"translated {block_type} {field}")
        written = save_rows(rows)
        self.stdout.write(
            f"Stored {written} translations, skipped {skipped} current or reviewed, "
            f"{len(failed)} not translated."
        )
        for item in failed:
            self.stdout.write(f"  not translated: {item}")
