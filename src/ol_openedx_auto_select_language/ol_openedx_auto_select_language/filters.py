"""
Filters for Open edX auto select language.
"""

from collections import OrderedDict

from django.conf import settings
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
        if (
            not getattr(settings, "ENABLE_AUTO_LANGUAGE_SELECTION", False)
            or block.scope_ids.block_type != VIDEO_BLOCK_TYPE
            or getattr(block, "ol_transcripts_restricted", False)
        ):
            return {"block": block, "context": context}

        original = block.get_transcripts_for_student

        def restricted(transcripts, dest_lang=None):
            """Return the student-view transcript info for one language only."""
            track_url, language, languages = original(
                transcripts=transcripts, dest_lang=dest_lang
            )
            if language in languages:
                languages = OrderedDict([(language, languages[language])])
            return track_url, language, languages

        block.get_transcripts_for_student = restricted
        block.ol_transcripts_restricted = True

        return {"block": block, "context": context}
