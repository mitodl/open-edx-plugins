"""
This block defines a Staff Graded Assignment.  Students are shown a rubric
and invited to upload a file which is then graded by staff.
"""
import hashlib
import json
import logging
import mimetypes
import pkg_resources

from functools import partial

from django.core.files import File
from django.core.files.storage import default_storage
from django.template.context import Context
from django.template.loader import get_template

from webob.response import Response

from xblock.core import XBlock
from xblock.fields import Scope, String, Float
from xblock.fragment import Fragment

log = logging.getLogger(__name__)


class StaffGradedAssignmentXBlock(XBlock):
    """
    This block defines a Staff Graded Assignment.  Students are shown a rubric
    and invited to upload a file which is then graded by staff.
    """
    has_score = True
    icon_class = 'problem'

    display_name = String(
        default='Staff Graded Assignment', scope=Scope.settings,
        help="This name appears in the horizontal navigation at the top of "
             "the page.")

    weight = Float(
        display_name="Problem Weight",
        help=("Defines the number of points each problem is worth. "
              "If the value is not set, the problem is worth the sum of the "
              "option point values."),
        values={"min": 0, "step": .1},
        scope=Scope.settings
    )

    points = Float(
        display_name="Maximum score",
        help=("Maximum grade score given to assignment by staff."),
        values={"min": 0, "step": .1},
        default=100,
        scope=Scope.settings
    )

    score = Float(
        display_name="Grade score",
        default=0,
        help=("Grade score given to assignment by staff."),
        values={"min": 0, "step": .1},
        scope=Scope.user_state
    )

    uploaded_sha1 = String(
        display_name="Upload SHA1",
        scope=Scope.user_state,
        default=None,
        help="sha1 of the file uploaded by the student for this assignment.")

    uploaded_filename = String(
        display_name="Upload file name",
        scope=Scope.user_state,
        default=None,
        help="The name of the file uploaded for this assignment.")

    uploaded_mimetype = String(
        display_name="Mime type of uploaded file",
        scope=Scope.user_state,
        default=None,
        help="The mimetype of the file uploaded for this assignment.")

    def max_score(self):
        return self.points

    def student_view(self, context=None):
        """
        The primary view of the StaffGradedAssignmentXBlock, shown to students
        when viewing courses.
        """
        template = get_template("staff_graded_assignment/show.html")
        fragment = Fragment(template.render(Context({
            "student_state": json.dumps(self.student_state())
        })))
        fragment.add_css(_resource("static/css/edx_sga.css"))
        fragment.add_javascript(_resource("static/js/src/edx_sga.js"))
        fragment.initialize_js('StaffGradedAssignmentXBlock')
        return fragment

    def student_state(self):
        """
        Returns a JSON serializable representation of student's state for
        rendering in client view.
        """
        if self.uploaded_sha1:
            uploaded = {
                "filename": self.uploaded_filename,
            }
        else:
            uploaded = None

        return {
            "uploaded": uploaded
        }

    def studio_view(self, context=None):
        try:
            cls = type(self)
            def none_to_empty(x):
                return x if x is not None else ''
            edit_fields = (
                (field, none_to_empty(getattr(self, field.name)), validator)
                for field, validator in (
                    (cls.display_name, 'string'),
                    (cls.points, 'number'),
                    (cls.weight, 'number')))

            template = get_template("staff_graded_assignment/edit.html")
            fragment = Fragment(template.render(Context({
                "fields": edit_fields
            })))
            fragment.add_javascript(_resource("static/js/src/studio.js"))
            fragment.initialize_js('StaffGradedAssignmentXBlock')
            return fragment
        except:
            log.error("Don't swallow my exceptions", exc_info=True)
            raise

    @XBlock.json_handler
    def save_sga(self, data, suffix=''):
        for name in ('display_name', 'points', 'weight'):
            setattr(self, name, data.get(name, getattr(self, name)))

    @XBlock.handler
    def upload_assignment(self, request, suffix=''):
        upload = request.params['assignment']
        self.uploaded_sha1 = _get_sha1(upload.file)
        self.uploaded_filename = upload.file.name
        self.uploaded_mimetype = mimetypes.guess_type(upload.file.name)[0]
        self._store_file(upload.file)
        return Response(json_body=self.student_state())

    @XBlock.handler
    def download_assignment(self, request, suffix=''):
        BLOCK_SIZE = 2**10 * 8 # 8kb
        upload = self._retrieve_file()
        app_iter = iter(partial(upload.read, BLOCK_SIZE), '')
        return Response(
            app_iter=app_iter,
            content_type=self.uploaded_mimetype,
            content_disposition="attachment; filename=" +
                self.uploaded_filename)

    def _file_storage_path(self):
        return '/'.join(filter(None, self.location[1:]) + (self.uploaded_sha1,))

    def _store_file(self, file):
        path = self._file_storage_path()
        if not default_storage.exists(path):
            default_storage.save(path, File(file))

    def _retrieve_file(self):
        path = self._file_storage_path()
        return default_storage.open(path)


def _get_sha1(file):
    BLOCK_SIZE = 2**10 * 8 # 8kb
    sha1 = hashlib.sha1()
    for block in iter(partial(file.read, BLOCK_SIZE), ''):
        sha1.update(block)
    file.seek(0)
    return sha1.hexdigest()


def _resource(path):
    """Handy helper for getting resources from our kit."""
    data = pkg_resources.resource_string(__name__, path)
    return data.decode("utf8")
