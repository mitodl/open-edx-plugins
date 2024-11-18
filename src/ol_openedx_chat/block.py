import pkg_resources
from django.template import Context, Template
from web_fragments.fragment import Fragment
from xblock.core import XBlockAside

BLOCK_PROBLEM_CATEGORY = "problem"
MULTIPLE_CHOICE_TYPE = "multiplechoiceresponse"


def get_resource_bytes(path):
    """
    Helper method to get the unicode contents of a resource in this repo.

    Args:
        path (str): The path of the resource

    Returns:
        unicode: The unicode contents of the resource at the given path
    """  # noqa: D401
    resource_contents = pkg_resources.resource_string(__name__, path)
    return resource_contents.decode("utf-8")


def render_template(template_path, context=None):
    """
    Evaluate a template by resource path, applying the provided context.
    """
    context = context or {}
    template_str = get_resource_bytes(template_path)
    template = Template(template_str)
    return template.render(Context(context))


class OLChatAside(XBlockAside):
    """
    XBlock aside that enables OL AI Chat functionality for an XBlock
    """

    @XBlockAside.aside_for("student_view")
    def student_view_aside(self, block, context=None):  # noqa: ARG002
        """
        Renders the aside contents for the student view
        """  # noqa: D401
        fragment = Fragment("")
        fragment.add_content(render_template("static/html/student_view.html"))
        return fragment

    @XBlockAside.aside_for("author_view")
    def author_view_aside(self, block, context=None):  # noqa: ARG002
        """
        Renders the aside contents for the author view
        """  # noqa: D401
        fragment = Fragment("")
        fragment.add_content(render_template("static/html/studio_view.html"))
        return fragment

    @classmethod
    def should_apply_to_block(cls, block):
        """
        Overrides base XBlockAside implementation. Indicates whether or not this aside
        should apply to a given block.

        Due to the different ways that the Studio and LMS runtimes construct XBlock
        instances, the problem type of the given block needs to be retrieved in
        different ways.
        """  # noqa: D401
        if getattr(block, "category", None) != BLOCK_PROBLEM_CATEGORY:
            return False
        block_problem_types = None
        # LMS passes in the block instance with `problem_types` as a property of
        # `descriptor`
        if hasattr(block, "descriptor"):
            block_problem_types = getattr(block.descriptor, "problem_types", None)
        # Studio passes in the block instance with `problem_types` as a top-level property  # noqa: E501
        elif hasattr(block, "problem_types"):
            block_problem_types = block.problem_types
        # We only want this aside to apply to the block if the problem is multiple
        # choice AND there are not multiple problem types.
        return block_problem_types == {MULTIPLE_CHOICE_TYPE}
