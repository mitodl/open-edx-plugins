"""Tests for the OLChatAside"""

from collections import defaultdict
from datetime import datetime, timedelta
from unittest.mock import Mock, PropertyMock, patch

import pytest
import pytz
from common.djangoapps.student.tests.factories import UserFactory
from dateutil.parser import parse as parse_datetime
from ddt import data, ddt, unpack
from opaque_keys.edx.keys import UsageKey
from ol_openedx_chat.block import OLChatAside
from ol_openedx_chat.constants import VIDEO_BLOCK_CATEGORY, PROBLEM_BLOCK_CATEGORY
from tests.utils import (
    RuntimeEnabledTestCase,
    make_scope_ids,
)
from django.conf import settings


@ddt
class OLChatAsideTests(RuntimeEnabledTestCase):
    """Tests for OLChatAside logic"""

    def setUp(self):
        super().setUp()
        self.problem_aside_usage_key = UsageKey.from_string(
            "aside-usage-v2:block-v1$:SGAU+SGA101+2017_SGA+type@problem+block"
            "@problem_4::ol_openedx_chat"
        )
        self.problem_scope_ids = make_scope_ids(self.problem_aside_usage_key)
        self.problem_aside_instance = OLChatAside(
            scope_ids=self.problem_scope_ids, runtime=self.runtime
        )

        self.video_aside_usage_key = UsageKey.from_string(
            "aside-usage-v2:block-v1$:SGAU+SGA101+2017_SGA+type@video+block"
            "@video_2::ol_openedx_chat"
        )
        self.video_scope_ids = make_scope_ids(self.video_aside_usage_key)
        self.video_aside_instance = OLChatAside(
            scope_ids=self.video_scope_ids, runtime=self.runtime
        )
        self.video_block.get_transcripts_info = Mock(return_value={"transcripts": {"en": "video-transcript-en.srt"}})

    @data(
        *[
            [True, True, PROBLEM_BLOCK_CATEGORY],
            [False, False, PROBLEM_BLOCK_CATEGORY],
            [True, True, VIDEO_BLOCK_CATEGORY],
            [False, False, VIDEO_BLOCK_CATEGORY],
        ]
    )
    @unpack
    @pytest.mark.django_db
    def test_student_view(self, ol_chat_enabled_value, should_render_aside, block_type):
        """
        Test that the aside student view returns a fragment if ol-chat is enabled.
        """
        aside_instance = self.problem_aside_instance if block_type == PROBLEM_BLOCK_CATEGORY else self.video_aside_instance
        aside_instance.ol_chat_enabled = ol_chat_enabled_value

        with patch(
            "ol_openedx_chat.block.OLChatAside.ol_chat_enabled",
            new=ol_chat_enabled_value,
        ), patch("ol_openedx_chat.block.Transcript.asset_location", return_value="video-transcript-en.srt"):
            block = self.problem_block if block_type == PROBLEM_BLOCK_CATEGORY else self.video_block
            fragment = aside_instance.student_view_aside(block)

            assert bool(fragment.content) is should_render_aside
            assert (
                fragment.js_init_fn == "AiChatAsideInit"
            ) is should_render_aside

            if not ol_chat_enabled_value:
                assert fragment.json_init_args is None
                assert fragment.js_init_fn is None
                assert fragment.content == ''
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

            assert (list(fragment.json_init_args.keys()) == expected_json_init_args_keys) is should_render_aside

            expected_request_body_keys = ["edx_module_id"]
            if block_type == PROBLEM_BLOCK_CATEGORY:
                expected_request_body_keys += ["block_siblings"]
                chat_api_url = "/http/tutor_agent/"

            elif block_type == VIDEO_BLOCK_CATEGORY:
                expected_request_body_keys += ["transcript_asset_id"]
                chat_api_url = "/http/video_gpt_agent/"

            assert (list(fragment.json_init_args["request_body"].keys()) == expected_request_body_keys) is should_render_aside
            assert (
                fragment.json_init_args["ask_tim_drawer_title"]
                == f"about {block.display_name}"
            ) is should_render_aside
            assert (fragment.json_init_args["user_id"] == self.runtime.user_id) is should_render_aside
            assert (fragment.json_init_args["block_id"] == block.usage_key.block_id) is should_render_aside
            assert (fragment.json_init_args["block_type"] == block_type) is should_render_aside
            assert (fragment.json_init_args["edx_module_id"] == block.usage_key) is should_render_aside
            assert (fragment.json_init_args["chat_api_url"] == chat_api_url) is should_render_aside
            assert (fragment.json_init_args["learning_mfe_base_url"] == settings.LEARNING_MICROFRONTEND_URL) is should_render_aside
            assert (fragment.json_init_args["request_body"]["edx_module_id"] == block.usage_key) is should_render_aside

            if block_type == PROBLEM_BLOCK_CATEGORY:
                assert (fragment.json_init_args["request_body"]["block_siblings"] == [block.usage_key for block in block.get_parent().get_children()]) is should_render_aside
            elif block_type == VIDEO_BLOCK_CATEGORY:
                assert (fragment.json_init_args["request_body"]["transcript_asset_id"] == "video-transcript-en.srt") is should_render_aside

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
        self, block_category, waffle_flag_enabled, other_course_setting_enabled, should_apply
    ):
        """
        Test that `should_apply_to_block` only True for problem
        and video blocks when `ol_openedx_chat.ol_openedx_chat_enabled` waffle flag is enabled
        and OL_OPENEDX_CHAT_VIDEO_BLOCK_ENABLED is enabled for Videos and OL_OPENEDX_CHAT_PROBLEM_BLOCK_ENABLED is enabled for problems.
        """
        with (
            patch("ol_openedx_chat.block.get_ol_openedx_chat_enabled_flag") as mock_get_ol_openedx_chat_enabled_flag,
            patch("ol_openedx_chat.block.is_ol_chat_enabled_for_course", return_value=other_course_setting_enabled)
        ):
            mock_get_ol_openedx_chat_enabled_flag.return_value = Mock(is_enabled=Mock(return_value=waffle_flag_enabled))
            block = self.problem_block if block_category == PROBLEM_BLOCK_CATEGORY else self.video_block
            aside_instance = self.problem_aside_instance if block_category == PROBLEM_BLOCK_CATEGORY else self.video_aside_instance
            assert aside_instance.should_apply_to_block(block) is should_apply

    # @data(True, False)  # noqa: FBT003
    # def test_studio_view(self, enabled_value):
    #     """
    #     Test that the aside studio view returns a fragment
    #     """
    #     self.aside_instance.enabled = enabled_value
    #     with patch(
    #         "rapid_response_xblock.block.RapidResponseAside.enabled",
    #         new=enabled_value,
    #     ):
    #         fragment = self.aside_instance.studio_view_aside(Mock())
    #         assert f'data-enabled="{enabled_value}"' in fragment.content
    #         assert fragment.js_init_fn == "RapidResponseAsideStudioInit"
    #
    # @data(True, False)  # noqa: FBT003
    # def test_author_view(self, enabled_value):
    #     """
    #     Test that the aside author view returns a fragment when enabled
    #     """
    #     self.aside_instance.enabled = enabled_value
    #     with patch(
    #         "rapid_response_xblock.block.RapidResponseAside.enabled",
    #         new=enabled_value,
    #     ), self.settings(ENABLE_RAPID_RESPONSE_AUTHOR_VIEW=True):
    #         fragment = self.aside_instance.author_view_aside(Mock())
    #         assert f'data-enabled="{enabled_value}"' in fragment.content
    #         assert fragment.js_init_fn == "RapidResponseAsideStudioInit"
    #
    # def test_toggle_block_open(self):
    #     """Test that toggle_block_open_status changes the status of a rapid response block"""  # noqa: E501
    #     usage_key = self.aside_instance.wrapped_block_usage_key
    #     course_key = self.aside_instance.course_key
    #     run = RapidResponseRun.objects.create(
    #         problem_usage_key=usage_key,
    #         course_key=course_key,
    #     )
    #     assert run.open is False
    #
    #     self.aside_instance.toggle_block_open_status(Mock())
    #     assert RapidResponseRun.objects.count() == 2  # noqa: PLR2004
    #     assert (
    #         RapidResponseRun.objects.filter(
    #             problem_usage_key=usage_key, course_key=course_key, open=True
    #         ).exists()
    #         is True
    #     )
    #
    #     self.aside_instance.toggle_block_open_status(Mock())
    #     assert RapidResponseRun.objects.count() == 2  # noqa: PLR2004
    #     assert (
    #         RapidResponseRun.objects.filter(
    #             problem_usage_key=usage_key, course_key=course_key, open=True
    #         ).exists()
    #         is False
    #     )
    #
    #     self.aside_instance.toggle_block_open_status(Mock())
    #     assert RapidResponseRun.objects.count() == 3  # noqa: PLR2004
    #     assert (
    #         RapidResponseRun.objects.filter(
    #             problem_usage_key=usage_key,
    #             course_key=course_key,
    #             open=True,
    #         ).exists()
    #         is True
    #     )
    #
