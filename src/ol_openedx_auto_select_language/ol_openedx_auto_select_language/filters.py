"""
Filters for Open edX auto select language.
"""

from collections import OrderedDict

from django.conf import settings
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx_filters import PipelineStep
from xmodule.modulestore.django import modulestore

from ol_openedx_auto_select_language.constants import (
    ENGLISH_LANGUAGE_CODE,
)
from ol_openedx_auto_select_language.utils import LanguageCode

VIDEO_BLOCK_TYPE = "video"


class AddDestLangForVideoBlock(PipelineStep):
    """
    Pipeline step to add destination language for video transcripts
    """

    def run_filter(self, context, student_view_context):
        """
        Add the destination language to the student view context if a video block
        with transcripts in the course language is found among the child blocks.
        """

        def set_dest_lang_for_video_block(block_key):
            """
            Set the destination language for video blocks with
            transcripts in the course language.
            """
            student_view_context["dest_lang"] = (
                ENGLISH_LANGUAGE_CODE  # default to English
            )
            video_block = modulestore().get_item(block_key)
            transcripts_info = video_block.get_transcripts_info()
            dest_lang = getattr(
                context.get("course", None), "language", ENGLISH_LANGUAGE_CODE
            )
            dest_lang = LanguageCode(dest_lang).to_bcp47()
            if (
                transcripts_info
                and transcripts_info.get("transcripts", {})
                and dest_lang in transcripts_info["transcripts"]
            ):
                student_view_context["dest_lang"] = dest_lang

        block = dict(context)["block"]
        block_usage_key = block.usage_key
        block_type = block_usage_key.block_type
        if block_type == "vertical":
            for child in getattr(block, "children", []):
                if child.block_type == VIDEO_BLOCK_TYPE:
                    set_dest_lang_for_video_block(child)
        elif block_type == VIDEO_BLOCK_TYPE:
            set_dest_lang_for_video_block(block_usage_key)

        return {"context": context, "student_view_context": student_view_context}


def _course_language(block):
    """
    Return the block's course language as a BCP47 code, or None.

    Read from the course rather than inferred from ``dest_lang``:
    ``AddDestLangForVideoBlock`` sets ``dest_lang`` to English whenever the
    course language is not an exact key in the video's transcripts, so on an
    ``es`` course with only ``en`` and ``fr`` transcripts ``dest_lang`` is
    ``en`` and would be mistaken for the course language. Reading the course
    per block also avoids the shared-context key that a vertical with several
    videos overwrites.
    """
    try:
        overview = CourseOverview.get_from_id(block.scope_ids.usage_id.course_key)
    except Exception:  # noqa: BLE001
        return None
    language = getattr(overview, "language", None)
    return LanguageCode(language).to_bcp47() if language else None


def _same_language(language, course_language):
    """
    Return True when two language codes share a primary subtag.

    Comparing primary subtags keeps the legitimate generalisations
    (``pt-BR`` resolving to ``pt``) without importing platform transcript
    helpers, whose module path differs between Open edX releases.
    """
    return language.split("-")[0].lower() == course_language.split("-")[0].lower()


class RestrictVideoTranscriptLanguages(PipelineStep):
    """
    Pipeline step to offer only the course-language transcript in the player.
    """

    def run_filter(self, block, context):
        """
        Narrow a video child block's transcript language list to one entry.

        The player's JS removes its language menu entirely when fewer than two
        languages are configured, so a single-entry list removes the control.

        `get_transcripts_for_student` is replaced on the instance rather than
        on the class, and is not an XBlock field, so nothing is marked dirty
        and the ``block.save()`` at the end of ``Runtime.render()`` stays a
        no-op. Writing to the ``transcripts`` field instead would raise
        ``InvalidScopeError``, because the LMS wraps authored scopes in
        ``ReadOnlyFieldData``.
        """
        original = getattr(block, "get_transcripts_for_student", None)
        if (
            not getattr(settings, "ENABLE_AUTO_LANGUAGE_SELECTION", False)
            or block.scope_ids.block_type != VIDEO_BLOCK_TYPE
            or getattr(block, "ol_transcripts_restricted", False)
            or original is None
        ):
            return {"block": block, "context": context}

        course_language = _course_language(block)
        if not course_language:
            return {"block": block, "context": context}

        def restricted(transcripts, dest_lang=None):
            """Return the student-view transcript info for one language only."""
            track_url, language, languages = original(
                transcripts=transcripts, dest_lang=dest_lang
            )
            if language in languages and _same_language(language, course_language):
                languages = OrderedDict([(language, languages[language])])
            return track_url, language, languages

        block.get_transcripts_for_student = restricted
        block.ol_transcripts_restricted = True

        return {"block": block, "context": context}
