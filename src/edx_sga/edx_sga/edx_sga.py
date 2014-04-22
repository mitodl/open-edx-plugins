"""TO-DO: Write a description of what this XBlock is."""

import pkg_resources

from xblock.core import XBlock
from xblock.fields import Scope, String, Float
from xblock.fragment import Fragment

from xmodule.progress import Progress


class StaffGradedAssignmentXBlock(XBlock):
    """
    This block defines a Staff Graded Assignment.  Students are shown a rubric
    and invited to upload a file which is then graded by staff.
    """
    has_score = True
    icon_class = 'problem'

    display_name = String(
        default='Staff Graded Assignment', scope=Scope.settings,
        help="Long title for the block.")

    weight = Float(
        display_name="Problem Weight",
        help=("Defines the number of points each problem is worth. "
              "If the value is not set, the problem is worth the sum of the "
              "option point values."),
        values={"min": 0, "step": .1},
        scope=Scope.settings
    )

    score = Float(
        display_name="Grade score",
        default=0,
        help=("Grade score given to assignment by staff."),
        values={"min": 0, "step": .1},
        scope=Scope.user_state
    )

    score_maximum = Float(
        display_name="Maximum score",
        help=("Maximum grade score given to assignment by staff."),
        values={"min": 0, "step": .1},
        default=100,
        scope=Scope.settings
    )

    def max_score(self):
        return self.score_maximum

    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

    # TO-DO: change this view to display your data your own way.
    def student_view(self, context=None):
        """
        The primary view of the StaffGradedAssignmentXBlock, shown to students
        when viewing courses.
        """
        html = self.resource_string("static/html/edx_sga.html")
        frag = Fragment(html.format(self=self))
        frag.add_css(self.resource_string("static/css/edx_sga.css"))
        frag.add_javascript(self.resource_string("static/js/src/edx_sga.js"))
        frag.initialize_js('StaffGradedAssignmentXBlock')
        return frag

    studio_view = student_view

    # TO-DO: change this handler to perform your own actions.  You may need more
    # than one handler, or you may not need any handlers at all.
    @XBlock.json_handler
    def increment_count(self, data, suffix=''):
        """
        An example handler, which increments the data.
        """
        # Just to show data coming in...
        assert data['hello'] == 'world'

        self.count += 1
        return {"count": self.count}
