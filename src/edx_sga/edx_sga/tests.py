import mock
import unittest

from xblock.field_data import DictFieldData


class StaffGradedAssignmentXblockTests(unittest.TestCase):

    def setUp(self):
        self.runtime = mock.Mock()
        self.scope_ids = mock.Mock()

    def _make_one(self, **kw):
        from edx_sga.sga import StaffGradedAssignmentXBlock as cls
        field_data = DictFieldData(kw)
        return cls(self.runtime, field_data, self.scope_ids)

    def test_ctor(self):
        block = self._make_one(points=10, score=9)
        self.assertEqual(block.display_name, "Staff Graded Assignment")
        self.assertEqual(block.points, 10)
        self.assertEqual(block.score, 9)

    def test_max_score(self):
        block = self._make_one(points=20)
        self.assertEqual(block.max_score(), 20)
