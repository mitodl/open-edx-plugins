from datetime import datetime
from unittest.mock import Mock

from ol_openedx_chat.constants import (
    PROBLEM_BLOCK_CATEGORY,
    VIDEO_BLOCK_CATEGORY,
)
from pytz import UTC
from xblock.runtime import DictKeyValueStore, KvsFieldData
from xblock.test.tools import TestRuntime
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import BlockFactory, CourseFactory


class OLChatTestCase(ModuleStoreTestCase):
    def setUp(self):
        super().setUp()

        key_store = DictKeyValueStore()
        field_data = KvsFieldData(key_store)
        self.runtime = TestRuntime(services={"field-data": field_data})

        course = CourseFactory.create(default_store=ModuleStoreEnum.Type.split)
        self.course = BlockFactory.create(
            parent_location=course.location,
            category="course",
            display_name="Test course",
        )
        self.chapter = BlockFactory.create(
            parent_location=self.course.location,
            category="chapter",
            display_name="Week 1",
            publish_item=True,
            start=datetime(2015, 3, 1, tzinfo=UTC),
        )
        self.sequential = BlockFactory.create(
            parent_location=self.chapter.location,
            category="sequential",
            display_name="Lesson 1",
            publish_item=True,
            start=datetime(2015, 3, 1, tzinfo=UTC),
        )
        self.vertical = BlockFactory.create(
            parent_location=self.sequential.location,
            category="vertical",
            display_name="Subsection 1",
            publish_item=True,
            start=datetime(2015, 4, 1, tzinfo=UTC),
        )

        self.problem_block = BlockFactory.create(
            category="problem",
            parent_location=self.vertical.location,
            display_name="A Problem Block",
            weight=1,
            user_id=self.user.id,
            publish_item=False,
        )
        self.video_block = BlockFactory.create(
            parent_location=self.vertical.location,
            category="video",
            display_name="My Video",
            user_id=self.user.id,
        )
        self.html_block = BlockFactory.create(
            category="html",
            parent_location=self.vertical.location,
            display_name="An HTML Block",
            user_id=self.user.id,
        )

        self.aside_name = "ol_openedx_chat"
        self.problem_aside_instance = self.create_aside(PROBLEM_BLOCK_CATEGORY)
        self.video_aside_instance = self.create_aside(VIDEO_BLOCK_CATEGORY)
        self.video_block.get_transcripts_info = Mock(
            return_value={"transcripts": {"en": "video-transcript-en.srt"}}
        )

    def create_aside(self, block_type):
        """
        Create an aside instance.
        """
        def_id = self.runtime.id_generator.create_definition(block_type)
        usage_id = self.runtime.id_generator.create_usage(def_id)
        _, aside_id = self.runtime.id_generator.create_aside(
            def_id, usage_id, self.aside_name
        )
        return self.runtime.get_aside(aside_id)
