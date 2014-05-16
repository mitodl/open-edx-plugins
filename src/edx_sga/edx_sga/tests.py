import json
import mock
import unittest

from xblock.field_data import DictFieldData


class DummyLocation(object):
    parts = ('foo', 'bar', 'baz')

    def url(self):
        (first, second), rest = self.parts[:2], self.parts[2:]
        return '{0}://{1}/{2}'.format(first, second, '/'.join(rest))

    def __iter__(self):
        return iter(self.parts)


class DummyResource(object):

    def __init__(self, path):
        self.path = path

    def __eq__(self, other):
        return isinstance(other, DummyResource) and self.path == other.path


class StaffGradedAssignmentXblockTests(unittest.TestCase):

    def setUp(self):
        self.runtime = mock.Mock()
        self.scope_ids = mock.Mock()

    def _make_one(self, **kw):
        from edx_sga.sga import StaffGradedAssignmentXBlock as cls
        field_data = DictFieldData(kw)
        block = cls(self.runtime, field_data, self.scope_ids)
        block.location = DummyLocation()
        block.xmodule_runtime = self.runtime
        return block

    def test_ctor(self):
        block = self._make_one(points=10, score=9)
        self.assertEqual(block.display_name, "Staff Graded Assignment")
        self.assertEqual(block.points, 10)
        self.assertEqual(block.score, 9)

    def test_max_score(self):
        block = self._make_one(points=20)
        self.assertEqual(block.max_score(), 20)

    @mock.patch('edx_sga.sga._resource', DummyResource)
    @mock.patch('edx_sga.sga.get_template')
    @mock.patch('edx_sga.sga.Fragment')
    def test_student_view(self, Fragment, get_template):
        block = self._make_one()
        fragment = block.student_view()
        get_template.assert_called_once_with(
            "staff_graded_assignment/show.html")
        context = get_template.return_value.render.call_args[0][0]
        self.assertEqual(context['is_course_staff'], True)
        self.assertEqual(context['id'], 'foo_bar_baz')
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
    @mock.patch('edx_sga.sga.get_template')
    @mock.patch('edx_sga.sga.Fragment')
    def test_student_view_publish_grade(self, Fragment, get_template):
        block = self._make_one(score=9, points=10, score_published=False)
        block.student_view()
        self.runtime.publish.assert_called_once_with(block, 'grade', {
            'value': 9, 'max_value': 10})
        self.assertEqual(block.score_published, True)

    @mock.patch('edx_sga.sga._resource', DummyResource)
    @mock.patch('edx_sga.sga.get_template')
    @mock.patch('edx_sga.sga.Fragment')
    def test_student_view_with_upload(self, Fragment, get_template):
        block = self._make_one(uploaded_sha1='foo', uploaded_filename='foo.bar')
        block.student_view()
        context = get_template.return_value.render.call_args[0][0]
        student_state = json.loads(context['student_state'])
        self.assertEqual(student_state['uploaded'], {'filename': 'foo.bar'})

    @mock.patch('edx_sga.sga._resource', DummyResource)
    @mock.patch('edx_sga.sga.get_template')
    @mock.patch('edx_sga.sga.Fragment')
    def test_student_view_with_annotated(self, Fragment, get_template):
        block = self._make_one(
            annotated_sha1='foo', annotated_filename='foo.bar')
        block.student_view()
        context = get_template.return_value.render.call_args[0][0]
        student_state = json.loads(context['student_state'])
        self.assertEqual(student_state['annotated'], {'filename': 'foo.bar'})

    @mock.patch('edx_sga.sga._resource', DummyResource)
    @mock.patch('edx_sga.sga.get_template')
    @mock.patch('edx_sga.sga.Fragment')
    def test_studio_view(self, Fragment, get_template):
        block = self._make_one()
        fragment = block.studio_view()
        get_template.assert_called_once_with(
            "staff_graded_assignment/edit.html")
        cls = type(block)
        context = get_template.return_value.render.call_args[0][0]
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
        block = self._make_one()
        block.save_sga(mock.Mock(body='{}'))
        self.assertEqual(block.display_name, "Staff Graded Assignment")
        self.assertEqual(block.points, 100)
        self.assertEqual(block.weight, None)
        block.save_sga(mock.Mock(body=json.dumps({
            "display_name": "Test Block",
            "points": 23,
            "weight": 11})))
        self.assertEqual(block.display_name, "Test Block")
        self.assertEqual(block.points, 23)
        self.assertEqual(block.weight, 11)
