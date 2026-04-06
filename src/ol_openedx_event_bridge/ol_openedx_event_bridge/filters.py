from openedx_filters import PipelineStep


class CreateMITCertificate(PipelineStep):
    """
    Pipeline step to create a certificate in the relevant MIT application
    when a user completes a course and gets a passing grade.

    Upon certificate creation, we will disable the creation in edX by raising
    an exception to prevent certificate creation in edX.
    """

    def run_filter(self, context, student_view_context):
        """
        Call MIT application to create certificate and raise exception to
        prevent edX certificate creation.

        Args:
            context(dict): dictionary containing the xBlock context
            student_view_context(dict): dictionary containing the student view context

        Returns:
            updated context dictionary with load_mathjax disabled
        """
