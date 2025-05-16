"""
Utils for ol-openedx-course-sync tests.
"""

from datetime import datetime

from pytz import UTC
from xblock.runtime import DictKeyValueStore, KvsFieldData
from xblock.test.tools import TestRuntime
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import BlockFactory, CourseFactory


class OLOpenedXCourseSyncTestCase(ModuleStoreTestCase):
    """
    Base test case for ol-openedx-course-sync tests.
    """

    def setUp(self):
        super().setUp()

        key_store = DictKeyValueStore()
        field_data = KvsFieldData(key_store)
        self.runtime = TestRuntime(services={"field-data": field_data})

        self.source_course = CourseFactory.create(
            default_store=ModuleStoreEnum.Type.split
        )
        self.source_course_block = BlockFactory.create(
            parent_location=self.source_course.location,
            category="course",
            display_name="Source course",
        )
        self.create_course_blocks(self.source_course_block)

        self.target_course = CourseFactory.create(
            default_store=ModuleStoreEnum.Type.split
        )
        self.target_course_block = BlockFactory.create(
            parent_location=self.target_course.location,
            category="course",
            display_name="Target course",
        )

    def create_course_blocks(self, course_block):
        """
        Create a set of blocks for the course.
        """
        chapter = BlockFactory.create(
            parent_location=course_block.location,
            category="chapter",
            display_name="Week 1",
            publish_item=True,
            start=datetime(2015, 3, 1, tzinfo=UTC),
        )
        sequential = BlockFactory.create(
            parent_location=chapter.location,
            category="sequential",
            display_name="Lesson 1",
            publish_item=True,
            start=datetime(2015, 3, 1, tzinfo=UTC),
        )
        vertical = BlockFactory.create(
            parent_location=sequential.location,
            category="vertical",
            display_name="Subsection 1",
            publish_item=True,
            start=datetime(2015, 4, 1, tzinfo=UTC),
        )

        BlockFactory.create(
            category="problem",
            parent_location=vertical.location,
            display_name="A Problem Block",
            weight=1,
            user_id=self.user.id,
            publish_item=False,
        )
        BlockFactory.create(
            parent_location=vertical.location,
            category="video",
            display_name="My Video",
            user_id=self.user.id,
        )
        BlockFactory.create(
            category="html",
            parent_location=vertical.location,
            display_name="An HTML Block",
            user_id=self.user.id,
        )
