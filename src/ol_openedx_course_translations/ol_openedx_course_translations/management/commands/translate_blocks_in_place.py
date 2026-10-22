"""
Translate a course's published blocks straight into BlockTranslation rows.

No translated copy of the course is made: every field listed in
``TRANSLATABLE_BLOCK_FIELDS`` is read from the modulestore, translated with an
LLM provider, has its answers, grading code, ids and keys copied back from the
source, and is stored as an ``auto`` row. Fields that already have a current
row (same source text) or a reviewed row are skipped, so running it again only
translates what changed. The course's grading type names are stored in one row
on the course block.

Video transcripts are added to edx-val, which every course using the same video
shares, for videos that have no transcript in the target language yet (existing
ones are replaced with ``--force-transcripts``). Videos without an
``edx_video_id`` or a transcript in the course language are skipped and listed.
"""

import json

import srt
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from ol_openedx_course_translations.blocks import (
    GRADER_LABELS_FIELD,
    TRANSLATABLE_BLOCK_FIELDS,
    grader_labels_source,
    json_string_value,
    restore_kept_parts,
    serialize,
    source_hash,
)
from ol_openedx_course_translations.management.commands.backfill_block_translations import (  # noqa: E501
    grader_labels_translation,
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
    decoded = json_string_value(block_type, field, source_value)
    if decoded is not None:
        return json.dumps(translate_value(provider, None, None, decoded, language))
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


def grader_labels_row(provider, course, source_pairs, language):
    """Return an unsaved row of the course's grading type names translated, or None."""
    terms = [term for pair in source_pairs for term in pair if term]
    # One call for every name, so the translated types stay distinct.
    mapping = provider.translate_grading_types(terms, language)
    translated_pairs = [
        [mapping.get(grader_type, grader_type), mapping.get(label, label)]
        for grader_type, label in source_pairs
    ]
    return grader_labels_translation(course, source_pairs, translated_pairs, language)


def translated_transcript(provider, transcript, language):
    """Return a transcript (``content``, ``file_format``) translated, in SJSON."""
    # The converter exists only inside edx-platform; it moved in newer releases.
    try:
        from openedx.core.djangoapps.video_config.transcripts_utils import (  # noqa: PLC0415
            Transcript,
            TranscriptsGenerationException,
        )
    except ImportError:
        from xmodule.video_block.transcripts_utils import (  # noqa: PLC0415
            Transcript,
            TranscriptsGenerationException,
        )

    content = transcript["content"]
    try:
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        source_srt = Transcript.convert(
            content,
            input_format=transcript["file_format"],
            output_format=Transcript.SRT,
        )
        subtitles = list(srt.parse(source_srt))
    except (
        UnicodeDecodeError,
        TranscriptsGenerationException,
        srt.SRTParseError,
    ) as error:
        raise ValueError(str(error)) from error
    if not subtitles:
        msg = "the source transcript has no cues"
        raise ValueError(msg)
    # Only the cue text is sent; cue count and timings are checked against the source,
    # and a mismatch raises ValueError. Provider errors (rate limits) propagate.
    subtitles = provider.translate_srt_with_validation(subtitles, language)
    return Transcript.convert(
        srt.compose(subtitles, reindex=False),
        input_format=Transcript.SRT,
        output_format=Transcript.SJSON,
    )


def translate_transcripts(provider, videos, source_language, language, *, force):
    """
    Add a translated transcript to edx-val for each video, saving each when done.

    edx-val keeps one transcript per video and language, shared by every course
    using the video. Return ``(translated, kept, not_translated)``: the edx video
    ids translated, the ids kept because they already have a transcript in the
    language, and a ``"<video> (<reason>)"`` line for each video not translated.
    A video whose transcript is missing or does not convert or validate is
    reported and the rest go on; other errors, such as provider rate limits, stop
    the run, keeping the transcripts saved before them.
    """
    from edxval import api as edxval_api  # noqa: PLC0415
    from edxval.exceptions import TranscriptNotFoundError  # noqa: PLC0415

    translated, kept, not_translated, seen = [], [], [], set()
    for video in videos:
        video_id = (video.edx_video_id or "").strip()
        if not video_id:
            not_translated.append(f"{video.location} (no edx_video_id)")
            continue
        # A video can be used by several blocks; it is translated once.
        if video_id in seen:
            continue
        seen.add(video_id)
        languages = edxval_api.get_available_transcript_languages(video_id)
        if language in languages and not force:
            kept.append(video_id)
            continue
        if source_language not in languages:
            not_translated.append(f"{video_id} (no {source_language} transcript)")
            continue
        try:
            metadata = edxval_api.get_video_transcript(video_id, source_language)
            data = edxval_api.get_video_transcript_data(video_id, source_language)
            if not metadata or not data:
                not_translated.append(f"{video_id} (no {source_language} transcript)")
                continue
            sjson = translated_transcript(
                provider,
                {"content": data["content"], "file_format": metadata["file_format"]},
                language,
            )
        except (TranscriptNotFoundError, ValueError) as error:
            not_translated.append(f"{video_id} ({type(error).__name__}: {error})")
            continue
        edxval_api.create_or_update_video_transcript(
            video_id,
            language,
            metadata={
                "provider": "Custom",
                "file_format": "sjson",
                "language_code": language,
            },
            file_data=ContentFile(sjson.encode("utf-8")),
        )
        translated.append(video_id)
    return translated, kept, not_translated


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
        parser.add_argument(
            "--force-transcripts",
            action="store_true",
            help=(
                "Replace video transcripts that already exist in the target language. "
                "They are shared by every course using the video."
            ),
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Translate the course's fields, grading type names and video transcripts."""
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
        published = ModuleStoreEnum.RevisionOption.published_only

        def published_blocks(block_type):
            return store.get_items(
                course_key, qualifiers={"category": block_type}, revision=published
            )

        course = published_blocks("course")[0]
        existing = {
            (usage_key, field): (row_hash, status)
            for usage_key, field, row_hash, status in BlockTranslation.objects.filter(
                course_key=course_key, language=language
            ).values_list("usage_key", "field", "source_hash", "status")
        }

        def needs_translation(location, field, source_value):
            row_hash, status = existing.get((location, field), (None, None))
            if status == BlockTranslation.Status.REVIEWED:
                return False
            return (
                options["force"]
                or status != BlockTranslation.Status.AUTO
                or row_hash != source_hash(source_value)
            )

        # Rows are added as they are translated and saved even if a provider
        # error stops the run, so a rerun does not pay for them again.
        rows = []
        try:
            skipped, failed = self.translate_fields(
                provider, published_blocks, language, needs_translation, rows
            )
            grader_skipped, grader_failed = self.translate_grader_labels(
                provider, course, language, needs_translation, rows
            )
            skipped += grader_skipped
            failed += grader_failed
        finally:
            written = save_rows(rows)
        self.stdout.write(
            f"Stored {written} translations, skipped {skipped} current or "
            f"reviewed, {len(failed)} not translated."
        )
        for item in failed:
            self.stdout.write(f"  not translated: {item}")

        source_language = getattr(course, "language", None) or settings.LANGUAGE_CODE
        if source_language == language:
            # The course's own transcripts are the source; never replace them.
            self.stdout.write(
                "Video transcripts not translated: the course is in that language."
            )
            return
        translated, kept, not_translated = translate_transcripts(
            provider,
            published_blocks("video"),
            source_language,
            language,
            force=options["force_transcripts"],
        )
        self.stdout.write(
            f"Added {len(translated)} video transcripts, kept {len(kept)} that "
            f"already exist, {len(not_translated)} not translated."
        )
        for item in not_translated:
            self.stdout.write(f"  transcript not translated: {item}")

    def translate_fields(
        self, provider, published_blocks, language, needs_translation, rows
    ):
        """Add rows for the translatable fields; return ``(skipped, failed)``."""
        skipped, failed = 0, []
        for block_type, fields in TRANSLATABLE_BLOCK_FIELDS.items():
            for block in published_blocks(block_type):
                for field in fields:
                    source_value = getattr(block, field, None)
                    if not source_value:
                        continue
                    if not needs_translation(block.location, field, source_value):
                        skipped += 1
                        continue
                    row = translated_row(provider, block, field, language)
                    if row is None:
                        failed.append(f"{block.location} {field}")
                    else:
                        rows.append(row)
                        self.stdout.write(f"translated {block_type} {field}")
        return skipped, failed

    def translate_grader_labels(
        self, provider, course, language, needs_translation, rows
    ):
        """Add the grading type names row when needed; return ``(skipped, failed)``."""
        source_pairs = grader_labels_source(course)
        if not source_pairs:
            return 0, []
        if not needs_translation(course.location, GRADER_LABELS_FIELD, source_pairs):
            return 1, []
        try:
            row = grader_labels_row(provider, course, source_pairs, language)
        except ValueError as error:
            # The provider gave two grading types the same name.
            return 0, [f"{course.location} {GRADER_LABELS_FIELD} ({error})"]
        if row is None:
            return 0, [f"{course.location} {GRADER_LABELS_FIELD}"]
        rows.append(row)
        self.stdout.write("translated course grading types")
        return 0, []
