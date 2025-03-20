"""Tests for the OLChatAside"""

import json
from datetime import datetime
from unittest.mock import Mock, patch

from ddt import data, ddt, unpack
from django.conf import settings
from django.test.client import Client
from django.urls import reverse
from ol_openedx_chat.block import OLChatAside
from ol_openedx_chat.constants import PROBLEM_BLOCK_CATEGORY, VIDEO_BLOCK_CATEGORY
from opaque_keys.edx.asides import AsideUsageKeyV2
from openedx.core.djangolib.testing.utils import skip_unless_cms, skip_unless_lms
from pytz import UTC
from xblock.core import XBlockAside
from xblock.runtime import DictKeyValueStore, KvsFieldData
from xblock.test.tools import TestRuntime
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import BlockFactory, CourseFactory


@ddt
class OLChatAsideTests(ModuleStoreTestCase):
    """Tests for OLChatAside logic"""

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

    @data(
        *[
            [True, True, PROBLEM_BLOCK_CATEGORY],
            [False, False, PROBLEM_BLOCK_CATEGORY],
            [True, True, VIDEO_BLOCK_CATEGORY],
            [False, False, VIDEO_BLOCK_CATEGORY],
        ]
    )
    @unpack
    @skip_unless_lms
    def test_student_view(self, ol_chat_enabled_value, should_render_aside, block_type):
        """
        Test that the aside student view returns a fragment if ol-chat is enabled.
        """
        aside_instance = (
            self.problem_aside_instance
            if block_type == PROBLEM_BLOCK_CATEGORY
            else self.video_aside_instance
        )
        aside_instance.ol_chat_enabled = ol_chat_enabled_value

        with patch(
            "ol_openedx_chat.block.OLChatAside.ol_chat_enabled",
            new=ol_chat_enabled_value,
        ), patch(
            "ol_openedx_chat.block.Transcript.asset_location",
            return_value="video-transcript-en.srt",
        ):
            block = (
                self.problem_block
                if block_type == PROBLEM_BLOCK_CATEGORY
                else self.video_block
            )
            fragment = aside_instance.student_view_aside(block)

            assert bool(fragment.content) is should_render_aside
            assert (fragment.js_init_fn == "AiChatAsideInit") is should_render_aside

            if not ol_chat_enabled_value:
                assert fragment.json_init_args is None
                assert fragment.js_init_fn is None
                assert fragment.content == ""
                return

            expected_json_init_args_keys = [
                "ask_tim_drawer_title",
                "user_id",
                "block_id",
                "block_type",
                "edx_module_id",
                "chat_api_url",
                "learning_mfe_base_url",
                "request_body",
            ]

            assert (
                list(fragment.json_init_args.keys()) == expected_json_init_args_keys
            ) is should_render_aside

            expected_request_body_keys = ["edx_module_id"]
            if block_type == PROBLEM_BLOCK_CATEGORY:
                expected_request_body_keys += ["block_siblings"]
                chat_api_url = "/http/tutor_agent/"

            elif block_type == VIDEO_BLOCK_CATEGORY:
                expected_request_body_keys += ["transcript_asset_id"]
                chat_api_url = "/http/video_gpt_agent/"

            assert (
                list(fragment.json_init_args["request_body"].keys())
                == expected_request_body_keys
            ) is should_render_aside
            assert (
                fragment.json_init_args["ask_tim_drawer_title"]
                == f"about {block.display_name}"
            ) is should_render_aside
            assert (
                fragment.json_init_args["user_id"] == self.runtime.user_id
            ) is should_render_aside
            assert (
                fragment.json_init_args["block_id"] == block.usage_key.block_id
            ) is should_render_aside
            assert (
                fragment.json_init_args["block_type"] == block_type
            ) is should_render_aside
            assert (
                fragment.json_init_args["edx_module_id"] == block.usage_key
            ) is should_render_aside
            assert (
                fragment.json_init_args["chat_api_url"] == chat_api_url
            ) is should_render_aside
            assert (
                fragment.json_init_args["learning_mfe_base_url"]
                == settings.LEARNING_MICROFRONTEND_URL
            ) is should_render_aside
            assert (
                fragment.json_init_args["request_body"]["edx_module_id"]
                == block.usage_key
            ) is should_render_aside

            if block_type == PROBLEM_BLOCK_CATEGORY:
                assert (
                    fragment.json_init_args["request_body"]["block_siblings"]
                    == [block.usage_key for block in block.get_parent().get_children()]
                ) is should_render_aside
            elif block_type == VIDEO_BLOCK_CATEGORY:
                assert (
                    fragment.json_init_args["request_body"]["transcript_asset_id"]
                    == "video-transcript-en.srt"
                ) is should_render_aside

    @data(
        *[
            [True, PROBLEM_BLOCK_CATEGORY],
            [False, PROBLEM_BLOCK_CATEGORY],
            [True, VIDEO_BLOCK_CATEGORY],
            [False, VIDEO_BLOCK_CATEGORY],
        ]
    )
    @unpack
    @skip_unless_cms
    def test_author_view(self, ol_chat_enabled_value, block_type):
        """
        Test that the aside author view returns a fragment.
        """
        aside_instance = (
            self.problem_aside_instance
            if block_type == PROBLEM_BLOCK_CATEGORY
            else self.video_aside_instance
        )
        aside_instance.ol_chat_enabled = ol_chat_enabled_value

        block = (
            self.problem_block
            if block_type == PROBLEM_BLOCK_CATEGORY
            else self.video_block
        )
        with patch(
            "ol_openedx_chat.block.OLChatAside.ol_chat_enabled",
            new=ol_chat_enabled_value,
        ):
            fragment = aside_instance.author_view_aside(block)

            assert bool(fragment.content)
            assert fragment.js_init_fn == "OLChatInit"

    @data(
        *[
            [PROBLEM_BLOCK_CATEGORY, True, True, True],
            [PROBLEM_BLOCK_CATEGORY, False, True, False],
            [PROBLEM_BLOCK_CATEGORY, True, False, False],
            [PROBLEM_BLOCK_CATEGORY, False, False, False],
            [VIDEO_BLOCK_CATEGORY, True, True, True],
            [VIDEO_BLOCK_CATEGORY, False, True, False],
            [VIDEO_BLOCK_CATEGORY, True, False, False],
            [VIDEO_BLOCK_CATEGORY, False, False, False],
        ]
    )
    @unpack
    def test_should_apply_to_block(
        self,
        block_category,
        waffle_flag_enabled,
        other_course_setting_enabled,
        should_apply,
    ):
        """
        Test that `should_apply_to_block` only True for problem
        and video blocks when `ol_openedx_chat.ol_openedx_chat_enabled`
        waffle flag is enabled and OL_OPENEDX_CHAT_VIDEO_BLOCK_ENABLED
        is enabled for Videos and OL_OPENEDX_CHAT_PROBLEM_BLOCK_ENABLED
        is enabled for problems.
        """
        with (
            patch(
                "ol_openedx_chat.block.get_ol_openedx_chat_enabled_flag"
            ) as mock_get_ol_openedx_chat_enabled_flag,
            patch(
                "ol_openedx_chat.block.is_ol_chat_enabled_for_course",
                return_value=other_course_setting_enabled,
            ),
        ):
            mock_get_ol_openedx_chat_enabled_flag.return_value = Mock(
                is_enabled=Mock(return_value=waffle_flag_enabled)
            )
            block = (
                self.problem_block
                if block_category == PROBLEM_BLOCK_CATEGORY
                else self.video_block
            )
            aside_instance = (
                self.problem_aside_instance
                if block_category == PROBLEM_BLOCK_CATEGORY
                else self.video_aside_instance
            )
            assert aside_instance.should_apply_to_block(block) is should_apply

    @data(
        *[
            [True, PROBLEM_BLOCK_CATEGORY],
            [False, PROBLEM_BLOCK_CATEGORY],
            [True, VIDEO_BLOCK_CATEGORY],
            [False, VIDEO_BLOCK_CATEGORY],
        ]
    )
    @unpack
    @skip_unless_cms
    @XBlockAside.register_temp_plugin(OLChatAside, "ol_chat_aside")
    def test_update_chat_config(self, ol_chat_enabled, block_category):
        """
        Tests that update_chat_config works properly
        """
        block = (
            self.problem_block
            if block_category == PROBLEM_BLOCK_CATEGORY
            else self.video_block
        )
        handler_name = "component_handler"
        usage_key = str(AsideUsageKeyV2(block.location, self.aside_name))
        kwargs_for_reverse = {
            "usage_key_string": str(usage_key),
            "handler": "update_chat_config",
        }
        handler_url = reverse(handler_name, kwargs=kwargs_for_reverse)

        client = Client()
        client.login(username=self.user.username, password=self.user_password)
        response = client.post(
            handler_url,
            json.dumps({"is_enabled": ol_chat_enabled}),
            content_type="application/json",
        )

        assert response.status_code == 200  # noqa: PLR2004
        with self.store.branch_setting(
            ModuleStoreEnum.Branch.draft_preferred, self.course.id
        ):
            block = self.store.get_item(block.location)
            ol_chat_aside = block.runtime.get_aside_of_type(block, self.aside_name)
            assert ol_chat_aside.ol_chat_enabled == ol_chat_enabled
