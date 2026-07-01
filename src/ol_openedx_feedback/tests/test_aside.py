"""Tests for the FeedbackAside trigger rendering and gating."""

from unittest.mock import Mock, patch

from ddt import data, ddt, unpack
from ol_openedx_feedback.block import FeedbackAside
from openedx.core.djangolib.testing.utils import skip_unless_lms

try:
    from xmodule.modulestore.xml import (
        XMLImportingModuleStoreRuntime as XMLImportingModuleStoreRuntime,  # noqa: PLC0414
    )
except ImportError:
    from xmodule.modulestore.xml import ImportSystem as XMLImportingModuleStoreRuntime

from tests.utils import OLFeedbackTestCase


@ddt
class FeedbackAsideTests(OLFeedbackTestCase):
    """Tests for FeedbackAside rendering and gating."""

    @data(
        *[
            [5, False, True],
            [None, False, False],
            [5, True, False],
        ]
    )
    @unpack
    @skip_unless_lms
    def test_student_view_aside(self, user_id, is_author_mode, should_render):
        """
        The trigger renders only for authenticated learners and never in
        Studio author/preview mode.
        """
        self.runtime.user_id = user_id
        self.runtime.is_author_mode = is_author_mode
        self.video_aside_instance.runtime = self.runtime

        fragment = self.video_aside_instance.student_view_aside(self.video_block)

        assert bool(fragment.content) is should_render
        if should_render:
            assert (
                f"ol-feedback-trigger-{self.video_block.usage_key.block_id}"
                in fragment.content
            )
            assert fragment.js_init_fn == "FeedbackAsideInit"
        else:
            assert fragment.content == ""
            assert fragment.js_init_fn is None

    @data(
        *[
            ["video", True, False, True],
            ["video", False, False, False],
            ["video", True, True, True],
            ["video", False, True, True],
            ["problem", True, False, True],
            ["vertical", True, False, False],
            ["vertical", False, False, False],
            ["vertical", True, True, False],
        ]
    )
    @unpack
    def test_should_apply_to_block(
        self, block_category, waffle_flag_enabled, is_import_runtime, should_apply
    ):
        """
        `should_apply_to_block` is True only for leaf blocks when the course
        waffle flag is enabled. During course import the block lacks course
        context, so the flag is skipped and only the block type is checked.
        """
        block = {
            "video": self.video_block,
            "problem": self.problem_block,
            "vertical": self.vertical,
        }[block_category]

        with patch(
            "ol_openedx_feedback.block.get_feedback_enabled_flag"
        ) as mock_get_feedback_enabled_flag:
            mock_get_feedback_enabled_flag.return_value = Mock(
                is_enabled=Mock(return_value=waffle_flag_enabled)
            )
            if is_import_runtime:
                block.runtime = Mock(spec=XMLImportingModuleStoreRuntime)

            assert FeedbackAside.should_apply_to_block(block) is should_apply
