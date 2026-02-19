"""
Filters for Open edX course translations.
"""

from openedx_filters import PipelineStep
from xmodule.modulestore.django import modulestore

from ol_openedx_course_translations.utils.constants import (
    ENGLISH_LANGUAGE_CODE,
)
from ol_openedx_course_translations.utils.course_translations import LanguageCode

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
