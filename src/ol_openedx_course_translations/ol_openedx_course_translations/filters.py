"""
Filters for Open edX course translations.
"""

from openedx_filters import PipelineStep
from xmodule.modulestore.django import modulestore

from ol_openedx_course_translations.utils.constants import (
    ENGLISH_LANGUAGE_CODE,
    ES_419_LANGUAGE_CODE,
    ES_LANGUAGE_CODE,
)

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
        for child in dict(context)["block"].children:
            if child.block_type == VIDEO_BLOCK_TYPE:
                student_view_context["dest_lang"] = (
                    ENGLISH_LANGUAGE_CODE  # default to English
                )
                video_block = modulestore().get_item(child)
                transcripts_info = video_block.get_transcripts_info()
                course_lang = getattr(
                    context.get("course", None), "language", ENGLISH_LANGUAGE_CODE
                )
                # Use 'es' for Spanish regardless of es-419
                dest_lang = (
                    ES_LANGUAGE_CODE
                    if course_lang == ES_419_LANGUAGE_CODE
                    else course_lang
                )
                if (
                    transcripts_info
                    and transcripts_info.get("transcripts", {})
                    and dest_lang in transcripts_info["transcripts"]
                ):
                    student_view_context["dest_lang"] = dest_lang
        return {"context": context, "student_view_context": student_view_context}
