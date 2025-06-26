"""Tests for the OLChatAside"""

import json
from unittest.mock import Mock, patch

from ddt import data, ddt, unpack
from django.conf import settings
from django.test.client import Client
from django.urls import reverse
from opaque_keys.edx.asides import AsideUsageKeyV2
from openedx.core.djangolib.testing.utils import skip_unless_cms, skip_unless_lms
from tests.utils import OLChatTestCase
from xblock.core import XBlockAside
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.xml import ImportSystem

from ol_openedx_chat.block import OLChatAside
from ol_openedx_chat.constants import (
    PROBLEM_BLOCK_CATEGORY,
    TUTOR_INITIAL_MESSAGES,
    VIDEO_BLOCK_CATEGORY,
)


@ddt
class OLChatAsideTests(OLChatTestCase):
    """Tests for OLChatAside logic"""

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

            if not should_render_aside:
                return

            expected_json_init_args_keys = [
                "block_id",
                "learning_mfe_base_url",
                "drawer_payload",
            ]
            assert list(fragment.json_init_args.keys()) == expected_json_init_args_keys

            expected_drawer_payload_keys = [
                "blockType",
                "title",
                "chat",
            ]
            if block_type == VIDEO_BLOCK_CATEGORY:
                expected_drawer_payload_keys += ["summary"]

            assert (
                list(fragment.json_init_args["drawer_payload"].keys())
                == expected_drawer_payload_keys
            )

            expected_drawer_payload_chat_keys = [
                "chatId",
                "initialMessages",
                "apiUrl",
                "requestBody",
                "userId",
            ]
            assert (
                list(fragment.json_init_args["drawer_payload"]["chat"].keys())
                == expected_drawer_payload_chat_keys
            )

            if block_type == VIDEO_BLOCK_CATEGORY:
                expected_drawer_payload_summary_keys = ["apiUrl"]
                assert (
                    list(fragment.json_init_args["drawer_payload"]["summary"].keys())
                    == expected_drawer_payload_summary_keys
                )

            expected_request_body_keys = ["edx_module_id"]
            if block_type == PROBLEM_BLOCK_CATEGORY:
                expected_request_body_keys += ["block_siblings"]
                chat_api_url = f"{settings.MIT_LEARN_AI_API_URL}/http/tutor_agent/"

            elif block_type == VIDEO_BLOCK_CATEGORY:
                expected_request_body_keys += ["transcript_asset_id"]
                chat_api_url = f"{settings.MIT_LEARN_AI_API_URL}/http/video_gpt_agent/"

            assert (
                list(
                    fragment.json_init_args["drawer_payload"]["chat"][
                        "requestBody"
                    ].keys()
                )
                == expected_request_body_keys
            )

            assert fragment.json_init_args["block_id"] == block.usage_key.block_id
            assert (
                fragment.json_init_args["learning_mfe_base_url"]
                == settings.LEARNING_MICROFRONTEND_URL
            )

            expected_request_body = {
                "edx_module_id": block.usage_key,
            }
            if block_type == PROBLEM_BLOCK_CATEGORY:
                expected_request_body["block_siblings"] = [
                    sibling.usage_key for sibling in block.get_parent().get_children()
                ]
            elif block_type == VIDEO_BLOCK_CATEGORY:
                expected_request_body["transcript_asset_id"] = "video-transcript-en.srt"

            expected_payload = {
                "blockType": block_type,
                "title": f"AskTIM about {block.display_name}",
                "chat": {
                    "chatId": block.usage_key.block_id,
                    "initialMessages": TUTOR_INITIAL_MESSAGES,
                    "apiUrl": chat_api_url,
                    "requestBody": expected_request_body,
                    "userId": self.runtime.user_id,
                },
            }
            if block_type == VIDEO_BLOCK_CATEGORY:
                expected_payload["summary"] = {
                    "apiUrl": f"{settings.MIT_LEARN_SUMMARY_FLASHCARD_URL}?edx_module_id=video-transcript-en.srt"  # noqa: E501
                }

            assert fragment.json_init_args["drawer_payload"] == expected_payload

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
            [PROBLEM_BLOCK_CATEGORY, True, True, True, True],
            [PROBLEM_BLOCK_CATEGORY, False, True, False, False],
            [PROBLEM_BLOCK_CATEGORY, True, False, False, False],
            [PROBLEM_BLOCK_CATEGORY, False, False, False, False],
            [PROBLEM_BLOCK_CATEGORY, False, False, True, True],
            [VIDEO_BLOCK_CATEGORY, True, True, True, True],
            [VIDEO_BLOCK_CATEGORY, False, True, False, False],
            [VIDEO_BLOCK_CATEGORY, True, False, False, False],
            [VIDEO_BLOCK_CATEGORY, False, False, False, False],
            [VIDEO_BLOCK_CATEGORY, False, False, True, True],
        ]
    )
    @unpack
    def test_should_apply_to_block(
        self,
        block_category,
        waffle_flag_enabled,
        other_course_setting_enabled,
        is_import_runtime,
        should_apply,
    ):
        """
        Test that `should_apply_to_block` only True for problem
        and video blocks when `ol_openedx_chat.ol_openedx_chat_enabled`
        waffle flag is enabled and OL_OPENEDX_CHAT_VIDEO_BLOCK_ENABLED
        is enabled for Videos and OL_OPENEDX_CHAT_PROBLEM_BLOCK_ENABLED
        is enabled for problems.
        """
        with patch(
            "ol_openedx_chat.block.get_ol_openedx_chat_enabled_flag"
        ) as mock_get_ol_openedx_chat_enabled_flag, patch(
            "ol_openedx_chat.block.is_ol_chat_enabled_for_course",
            return_value=other_course_setting_enabled,
        ):
            mock_get_ol_openedx_chat_enabled_flag.return_value = Mock(
                    is_enabled=Mock(return_value=waffle_flag_enabled)
                )
            block = (
                self.problem_block
                if block_category == PROBLEM_BLOCK_CATEGORY
                else self.video_block
            )

            if is_import_runtime:
                block.runtime = Mock(spec=ImportSystem)

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
