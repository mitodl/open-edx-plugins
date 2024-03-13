"""Utility functions and classes for the rapid response test suite"""
from contextlib import contextmanager
import os
import shutil
import tempfile
from unittest.mock import Mock, patch

from django.http.request import HttpRequest

from xblock.fields import ScopeIds
from xblock.runtime import DictKeyValueStore, KvsFieldData
from xblock.test.tools import TestRuntime
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import BlockFactory
from xmodule.modulestore.xml_importer import import_course_from_xml
from xmodule.capa_block import ProblemBlock

from lms.djangoapps.courseware.block_render import (
    prepare_runtime_for_user,
    make_track_function,
)
from common.djangoapps.student.tests.factories import AdminFactory, StaffFactory

BASE_DIR = os.path.dirname(os.path.realpath(__file__))


def make_scope_ids(usage_key):
    """
    Make scope ids

    Args:
        runtime (xblock.runtime.Runtime): A runtime
        usage_key (opaque_keys.edx.keys.UsageKey): A usage key

    Returns:
        xblock.fields.ScopeIds: A ScopeIds object for the block for usage_key
    """
    block_type = 'fake'
    runtime = TestRuntime(services={'field-data': KvsFieldData(kvs=DictKeyValueStore())})
    def_id = runtime.id_generator.create_definition(block_type)
    return ScopeIds(
        'user', block_type, def_id, usage_key
    )


def combine_dicts(dictionary, extras):
    """
    Similar to {**dictionary, **extras} in Python 3

    Args:
        dictionary (dict): A dictionary
        extras (dict): Another dictionary

    Returns:
        dict: A new dictionary with both key and value pairs
    """
    ret = dict(dictionary)
    ret.update(extras)
    return ret


class RuntimeEnabledTestCase(ModuleStoreTestCase):
    """
    Test class that sets up a course, instructor, runtime, and other
    commonly-needed objects for testing XBlocks
    """

    def setUp(self):
        super().setUp()

        self.track_function = make_track_function(HttpRequest())
        self.student_data = Mock()
        self.staff = AdminFactory.create()
        self.course = self.import_test_course()
        self.block = BlockFactory(category="pure", parent=self.course)
        self.course_id = self.course.id
        self.instructor = StaffFactory.create(course_key=self.course_id)
        self.runtime = self.make_runtime()
        self.course.bind_for_student(self.instructor)

    def make_runtime(self, **kwargs):
        """
        Make a runtime
        """
        prepare_runtime_for_user(
            user=self.instructor,
            student_data=self.student_data,
            runtime=self.block.runtime,
            course_id=self.course.id,
            track_function=self.track_function,
            request_token=Mock(),
            course=self.course,
            **kwargs
        )
        return self.block.runtime

    def import_test_course(self):
        """
        Import the test course with the sga unit
        """
        # adapted from edx-platform/cms/djangoapps/contentstore/
        # management/commands/tests/test_cleanup_assets.py
        input_dir = os.path.join(BASE_DIR, "..", "test_data")

        temp_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(temp_dir))

        xml_dir = os.path.join(temp_dir, "xml")
        shutil.copytree(input_dir, xml_dir)

        store = modulestore()
        courses = import_course_from_xml(
            store,
            self.staff.id,
            xml_dir,
            create_if_not_present=True,
        )
        return courses[0]

    @contextmanager
    def patch_modulestore(self):
        """
        Set xmodule_runtime and xmodule_runtime.xmodule_instance on blocks retrieved from the modulestore.

        Only applies if get_item is used.
        """
        store = modulestore()

        def wrap_runtime(*args, **kwargs):
            """Alter modulestore to set xmodule_runtime and xmodule_runtime.xmodule_instance"""
            block = store.get_item(*args, **kwargs)
            block.runtime = self.runtime

            # Copied this from xmodule.xmodule.x_module._xmodule
            # When it executes there it raises a scope error, but here it's fine. Not sure what the difference is
            block.xmodule_runtime.xmodule_instance = block.runtime.construct_xblock_from_class(
                ProblemBlock,
                scope_ids=block.scope_ids,
                field_data=block._field_data,  # pylint: disable=protected-access
                for_parent=block.get_parent()
            )

            return block

        with patch('rapid_response_xblock.block.modulestore', autospec=True) as modulestore_mock:
            modulestore_mock.return_value.get_item.side_effect = wrap_runtime
            yield modulestore_mock

    def get_problem_by_id(self, problem_id):
        """
        Get a problem from the modulestore and assign the runtime

        Args:
            problem_id (UsageKey): A usage key for a problem

        Returns:
            CapaDescriptor: A problem
        """
        store = modulestore()
        problem = store.get_item(problem_id)
        problem.xmodule_runtime = self.runtime
        return problem
