"""
Filters for Open edX course translations.
"""
from openedx_filters import PipelineStep
from xmodule.modulestore.django import modulestore


class AddDestLangForVideoBlock(PipelineStep):
    """
    Pipeline step to add destination language for video transcripts
    """

    def run_filter(self, context, student_view_context):  # noqa: ARG002
        """
        Adds the destination language to the student view context if a video block
        with transcripts in the course language is found among the child blocks.
        """
        for child in dict(context)["block"].children:
            if child.block_type == "video":
                video_block = modulestore().get_item(child)
                transcripts_info = video_block.get_transcripts_info()
                course_lang = getattr(context.get("course", None), "language", "en")
                if transcripts_info and transcripts_info.get("transcripts", {}) and course_lang in transcripts_info["transcripts"]:
                    student_view_context["dest_lang"] = course_lang
        return context, student_view_context
