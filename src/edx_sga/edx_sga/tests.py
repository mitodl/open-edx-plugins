import datetime
import json
import mock
import os
import pkg_resources
import pytz
import tempfile
import unittest

from courseware.models import StudentModule
from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage
from student.models import UserProfile
from xblock.field_data import DictFieldData
from opaque_keys.edx.locations import Location, SlashSeparatedCourseKey


class DummyResource(object):

    def __init__(self, path):
        self.path = path

    def __eq__(self, other):
        return isinstance(other, DummyResource) and self.path == other.path


class DummyUpload(object):

    def __init__(self, path, name):
        self.stream = open(path, 'rb')
        self.name = name
        self.size = os.path.getsize(path)

    def read(self, n=None):
        return self.stream.read(n)

    def seek(self, n):
        return self.stream.seek(n)


class StaffGradedAssignmentXblockTests(unittest.TestCase):

    def setUp(self):
        self.course_id = SlashSeparatedCourseKey.from_deprecated_string(
            'foo/bar/baz'
        )
        self.runtime = mock.Mock(course_id=self.course_id)
        self.scope_ids = mock.Mock()
        tmp = tempfile.mkdtemp()
        patcher = mock.patch(
            "edx_sga.sga.default_storage",
            FileSystemStorage(tmp))
        patcher.start()
        self.addCleanup(patcher.stop)

    def make_one(self, **kw):
        from edx_sga.sga import StaffGradedAssignmentXBlock as cls
        field_data = DictFieldData(kw)
        block = cls(self.runtime, field_data, self.scope_ids)
        block.location = Location(
            'org', 'course', 'run', 'category', 'name', 'revision'
        )
        block.xmodule_runtime = self.runtime
        return block

    def make_student_module(self, block, name, **state):
        user = User(username=name)
        user.save()
        profile = UserProfile(user=user, name=name)
        profile.save()
        module = StudentModule(
            module_state_key=block.location,
            student=user,
            course_id=self.course_id,
            state=json.dumps(state))
        module.save()

        self.addCleanup(profile.delete)
        self.addCleanup(module.delete)
        self.addCleanup(user.delete)

        return module

    def personalize(self, block, student_module):
        student_module = StudentModule.objects.get(pk=student_module.id)
        state = json.loads(student_module.state)
        for k, v in state.items():
            setattr(block, k, v)

    def test_ctor(self):
        block = self.make_one(points=10, score=9)
        self.assertEqual(block.display_name, "Staff Graded Assignment")
        self.assertEqual(block.points, 10)
        self.assertEqual(block.score, 9)

    def test_max_score(self):
        block = self.make_one(points=20)
        self.assertEqual(block.max_score(), 20)

    @mock.patch('edx_sga.sga._resource', DummyResource)
    @mock.patch('edx_sga.sga.render_template')
    @mock.patch('edx_sga.sga.Fragment')
    def test_student_view(self, Fragment, render_template):
        block = self.make_one()
        fragment = block.student_view()
        render_template.assert_called_once
        template_arg = render_template.call_args[0][0]
        self.assertEqual(
            template_arg,
            'templates/staff_graded_assignment/show.html'
        )
        context = render_template.call_args[0][1]
        self.assertEqual(context['is_course_staff'], True)
        self.assertEqual(context['id'], 'name')
        student_state = json.loads(context['student_state'])
        self.assertEqual(student_state['uploaded'], None)
        self.assertEqual(student_state['annotated'], None)
        self.assertEqual(student_state['upload_allowed'], True)
        self.assertEqual(student_state['published'], True)
        self.assertEqual(student_state['max_score'], 100)
        self.assertEqual(student_state['graded'], None)
        fragment.add_css.assert_called_once_with(
            DummyResource("static/css/edx_sga.css"))
        fragment.add_javascript.assert_called_once_with(
            DummyResource("static/js/src/edx_sga.js"))
        fragment.initialize_js.assert_called_once_with(
            "StaffGradedAssignmentXBlock")

    @mock.patch('edx_sga.sga._resource', DummyResource)
    @mock.patch('edx_sga.sga.Fragment')
    def test_student_view_publish_grade(self, Fragment):
        block = self.make_one(score=9, points=10, score_published=False)
        block.student_view()
        self.runtime.publish.assert_called_once_with(block, 'grade', {
            'value': 9, 'max_value': 10})
        self.assertEqual(block.score_published, True)

    @mock.patch('edx_sga.sga._resource', DummyResource)
    @mock.patch('edx_sga.sga.render_template')
    @mock.patch('edx_sga.sga.Fragment')
    def test_student_view_with_upload(self, Fragment, render_template):
        block = self.make_one(uploaded_sha1='foo', uploaded_filename='foo.bar')
        block.student_view()
        context = render_template.call_args[0][1]
        student_state = json.loads(context['student_state'])
        self.assertEqual(student_state['uploaded'], {'filename': 'foo.bar'})

    @mock.patch('edx_sga.sga._resource', DummyResource)
    @mock.patch('edx_sga.sga.render_template')
    @mock.patch('edx_sga.sga.Fragment')
    def test_student_view_with_annotated(self, Fragment, render_template):
        block = self.make_one(
            annotated_sha1='foo', annotated_filename='foo.bar')
        block.student_view()
        context = render_template.call_args[0][1]
        student_state = json.loads(context['student_state'])
        self.assertEqual(student_state['annotated'], {'filename': 'foo.bar'})

    @mock.patch('edx_sga.sga._resource', DummyResource)
    @mock.patch('edx_sga.sga.render_template')
    @mock.patch('edx_sga.sga.Fragment')
    def test_studio_view(self, Fragment, render_template):
        block = self.make_one()
        fragment = block.studio_view()
        render_template.assert_called_once
        template_arg = render_template.call_args[0][0]
        self.assertEqual(
            template_arg,
            'templates/staff_graded_assignment/edit.html'
        )
        cls = type(block)
        context = render_template.call_args[0][1]
        self.assertEqual(tuple(context['fields']), (
            (cls.display_name, 'Staff Graded Assignment', 'string'),
            (cls.points, 100, 'number'),
            (cls.weight, '', 'number')
        ))
        fragment.add_javascript.assert_called_once_with(
            DummyResource("static/js/src/studio.js"))
        fragment.initialize_js.assert_called_once_with(
            "StaffGradedAssignmentXBlock")

    def test_save_sga(self):
        block = self.make_one()
        block.save_sga(mock.Mock(body='{}'))
        self.assertEqual(block.display_name, "Staff Graded Assignment")
        self.assertEqual(block.points, 100)
        self.assertEqual(block.weight, None)
        block.save_sga(mock.Mock(method="POST", body=json.dumps({
            "display_name": "Test Block",
            "points": 23,
            "weight": 11})))
        self.assertEqual(block.display_name, "Test Block")
        self.assertEqual(block.points, 23)
        self.assertEqual(block.weight, 11)

    def test_upload_download_assignment(self):
        path = pkg_resources.resource_filename(__package__, 'tests.py')
        expected = open(path, 'rb').read()
        upload = mock.Mock(file=DummyUpload(path, 'test.txt'))
        block = self.make_one()
        block.upload_assignment(mock.Mock(params={'assignment': upload}))
        response = block.download_assignment(None)
        self.assertEqual(response.body, expected)

    def test_staff_upload_download_annotated(self):
        path = pkg_resources.resource_filename(__package__, 'tests.py')
        expected = open(path, 'rb').read()
        upload = mock.Mock(file=DummyUpload(path, 'test.txt'))
        block = self.make_one()
        fred = self.make_student_module(block, "fred1")
        block.staff_upload_annotated(mock.Mock(params={
            'annotated': upload,
            'module_id': fred.id}))
        response = block.staff_download_annotated(mock.Mock(params={
            'module_id': fred.id}))
        self.assertEqual(response.body, expected)

    def test_download_annotated(self):
        path = pkg_resources.resource_filename(__package__, 'tests.py')
        expected = open(path, 'rb').read()
        upload = mock.Mock(file=DummyUpload(path, 'test.txt'))
        block = self.make_one()
        fred = self.make_student_module(block, "fred2")
        block.staff_upload_annotated(mock.Mock(params={
            'annotated': upload,
            'module_id': fred.id}))
        self.personalize(block, fred)
        response = block.download_annotated(None)
        self.assertEqual(response.body, expected)

    def test_staff_download(self):
        path = pkg_resources.resource_filename(__package__, 'tests.py')
        expected = open(path, 'rb').read()
        upload = mock.Mock(file=DummyUpload(path, 'test.txt'))
        block = self.make_one()
        block.upload_assignment(mock.Mock(params={'assignment': upload}))
        fred = self.make_student_module(
            block, "fred3",
            uploaded_sha1=block.uploaded_sha1,
            uploaded_filename=block.uploaded_filename,
            uploaded_mimetype=block.uploaded_mimetype)
        response = block.staff_download(mock.Mock(params={
            'module_id': fred.id}))
        self.assertEqual(response.body, expected)

    def test_get_staff_grading_data(self):
        block = self.make_one()
        barney = self.make_student_module(
            block, "barney",
            uploaded_filename="foo.txt",
            score=10,
            annotated_filename="foo_corrected.txt",
            comment="Good work!")
        fred = self.make_student_module(block, "fred4")
        data = block.get_staff_grading_data(None).json_body
        assignments = sorted(data['assignments'], key=lambda x: x['username'])
        self.assertEqual(assignments[0]['module_id'], barney.id)
        self.assertEqual(assignments[0]['username'], 'barney')
        self.assertEqual(assignments[0]['fullname'], 'barney')
        self.assertEqual(assignments[0]['filename'], 'foo.txt')
        self.assertEqual(assignments[0]['score'], 10)
        self.assertEqual(assignments[0]['annotated'], 'foo_corrected.txt')
        self.assertEqual(assignments[0]['comment'], 'Good work!')
        self.assertEqual(assignments[1]['module_id'], fred.id)
        self.assertEqual(assignments[1]['username'], 'fred4')
        self.assertEqual(assignments[1]['fullname'], 'fred4')
        self.assertEqual(assignments[1]['filename'], None)
        self.assertEqual(assignments[1]['score'], None)
        self.assertEqual(assignments[1]['annotated'], None)
        self.assertEqual(assignments[1]['comment'], '')

    def test_enter_grade(self):
        block = self.make_one()
        fred = self.make_student_module(block, "fred5")
        block.enter_grade(mock.Mock(params={
            'module_id': fred.id,
            'grade': 9,
            'comment': "Good!"}))
        state = json.loads(StudentModule.objects.get(pk=fred.id).state)
        self.assertEqual(state['score'], 9)
        self.assertEqual(state['comment'], 'Good!')

    def test_remove_grade(self):
        block = self.make_one()
        fred = self.make_student_module(
            block, "fred6", grade=9, comment='Good!')
        block.remove_grade(mock.Mock(params={'module_id': fred.id}))
        state = json.loads(StudentModule.objects.get(pk=fred.id).state)
        self.assertEqual(state['score'], None)
        self.assertEqual(state['comment'], '')

    def test_past_due(self):
        block = self.make_one()
        block.due = datetime.datetime(2010, 5, 12, 2, 42, tzinfo=pytz.utc)
        self.assertTrue(block.past_due())
