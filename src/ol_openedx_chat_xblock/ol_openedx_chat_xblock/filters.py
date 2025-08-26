from openedx_filters import PipelineStep


class DisableMathJaxForOLChatBlock(PipelineStep):
    """
    Pipeline step to disable MathJax loading for OLChatBlock instances.

    This class checks if any child block is of type 'ol_openedx_chat_xblock'
    and sets 'load_mathjax' to False in the context if found.
    """

    def run_filter(self, context, student_view_context):  # noqa: ARG002
        """
        Disables MathJax loading in the context if any child block is of type
        'ol_openedx_chat_xblock'.

        Args:
            context(dict): dictionary containing the xBlock context
            student_view_context(dict): dictionary containing the student view context

        Returns:
            updated context dictionary with load_mathjax disabled
        """

        for child in dict(context)["block"].children:
            if child.block_type == __package__:
                context["load_mathjax"] = False
                break
        return context
