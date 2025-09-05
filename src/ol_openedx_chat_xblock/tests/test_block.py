"""Tests for OLChatXBlock"""

import json
from unittest.mock import Mock, PropertyMock, patch

import requests
from ddt import data, ddt, unpack
from django.test import override_settings
from opaque_keys.edx.keys import UsageKey
from rest_framework import status as api_status
from web_fragments.fragment import Fragment
from webob.request import Request
from webob.response import Response
from xblock.field_data import DictFieldData
from xblock.fields import ScopeIds
from xblock.test.tools import TestRuntime
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase

from ol_openedx_chat_xblock.block import (
    OLChatXBlock,
    generate_canvas_course_id,
    get_resource_bytes,
    render_template,
)
from ol_openedx_chat_xblock.constants import (
    CHAT_XBLOCK_BLOCK_ID,
    CHAT_XBLOCK_THREAD_ID,
    COOKIE_NAME_CHAT_XBLOCK,
    COOKIE_NAME_SYLLABUS_ANON,
    COOKIE_NAME_TUTOR_ANON,
    XBLOCK_TYPE_SYLLABUS,
    XBLOCK_TYPE_TUTOR,
)


@override_settings(
    MIT_LEARN_AI_XBLOCK_CHAT_API_URL="http://mittestchat.com/api",
    MIT_LEARN_AI_XBLOCK_TUTOR_API_URL="http://mittesttutor.com/api",
    MIT_LEARN_AI_XBLOCK_CHAT_API_TOKEN="test_token",  # noqa: S106
    MIT_LEARN_AI_XBLOCK_PROBLEM_SET_LIST_URL="http://test.com/list/",
)
@ddt
class OLChatXBlockTest(ModuleStoreTestCase):
    """Test cases for OLChatXBlock."""

    def setUp(self):
        """Set up test fixtures."""
        self.runtime = TestRuntime(services={})
        usage_key = UsageKey.from_string(
            "block-v1:TestOrg+TestCourse+2024+type@yourxblock+block@test123"
        )

        self.scope_ids = ScopeIds(
            user_id="student",
            block_type=usage_key.block_type,
            def_id=usage_key,
            usage_id=usage_key,
        )
        self.field_data = DictFieldData({})

        self.xblock = OLChatXBlock(
            runtime=self.runtime,
            field_data=self.field_data,
            scope_ids=self.scope_ids,
        )
        self.xblock.course_id = "test_course_123"

    def test_block_defaults(self):
        """Test that course_id has correct default value."""
        test_xblock = OLChatXBlock(
            runtime=self.runtime,
            field_data=DictFieldData({}),
            scope_ids=self.scope_ids,
        )
        assert test_xblock.display_name == "OL Chat XBlock"
        assert test_xblock.course_id == ""
        assert not test_xblock.is_tutor_xblock
        assert test_xblock.learn_readable_course_id == ""

    def test_editable_fields(self):
        """Test that editable_fields contains expected fields."""
        assert self.xblock.editable_fields == (
            "display_name",
            "course_id",
            "is_tutor_xblock",
        )

    @patch("ol_openedx_chat_xblock.block.get_resource_bytes")
    @patch("ol_openedx_chat_xblock.block.render_template")
    def test_student_view(self, mock_render_template, mock_get_resource_bytes):
        """Test student_view method."""
        mock_render_template.return_value = "<div>Student View</div>"
        mock_get_resource_bytes.side_effect = ["js_content", "css_content"]

        fragment = self.xblock.student_view()
        assert isinstance(fragment, Fragment)
        mock_render_template.assert_called_once_with(
            "static/html/student_view.html",
            {"block_id": self.xblock.usage_key.block_id},
        )

    @patch("ol_openedx_chat_xblock.block.get_resource_bytes")
    @patch("ol_openedx_chat_xblock.block.render_template")
    def test_author_view(self, mock_render_template, mock_get_resource_bytes):
        """Test author_view method."""
        mock_render_template.return_value = "<div>Author View</div>"
        mock_get_resource_bytes.side_effect = ["js_content", "css_content"]

        fragment = self.xblock.author_view()

        assert isinstance(fragment, Fragment)
        mock_render_template.assert_called_once_with(
            "static/html/studio_view.html", {"block_id": self.xblock.usage_key.block_id}
        )

    def test_ol_chat_invalid_json(self):
        """Test ol_chat with invalid JSON request."""
        # Creating a real webob Request object
        environ = {
            "REQUEST_METHOD": "POST",
            "wsgi.input": Mock(),
            "CONTENT_TYPE": "application/json",
        }
        request = Request(environ)

        # Patch the .json property to raise an Exception
        with patch.object(Request, "json", new_callable=PropertyMock) as mock_json:
            mock_json.side_effect = Exception("Invalid JSON")
            response = self.xblock.ol_chat(request)
            assert isinstance(response, Response)
            assert response.status_int == api_status.HTTP_400_BAD_REQUEST
            assert b"Invalid request body. Expected JSON." in response.body

    @override_settings(
        MIT_LEARN_AI_XBLOCK_CHAT_API_URL="", MIT_LEARN_AI_XBLOCK_CHAT_API_TOKEN=""
    )
    def test_ol_chat_missing_api_config(self):
        """Test ol_chat with missing API configuration."""
        request_mock = Mock()
        request_mock.json = {"message": "test message"}

        response = self.xblock.ol_chat(request_mock)

        assert isinstance(response, Response)
        assert response.status_int == api_status.HTTP_400_BAD_REQUEST
        assert b"Missing API configurations" in response.body

    def test_ol_chat_missing_course_id(self):
        """Test ol_chat with missing course_id."""
        self.xblock.course_id = ""
        request_mock = Mock()
        request_mock.json = {"message": "test message"}

        response = self.xblock.ol_chat(request_mock)

        assert isinstance(response, Response)
        assert response.status_int == api_status.HTTP_400_BAD_REQUEST
        assert b"Course ID is required" in response.body

    def test_ol_chat_empty_message(self):
        """Test ol_chat with empty message."""
        request_mock = Mock()
        request_mock.json = {"message": "   "}

        response = self.xblock.ol_chat(request_mock)

        assert isinstance(response, Response)
        assert response.status_int == api_status.HTTP_400_BAD_REQUEST
        assert b"Message field is required" in response.body

    @patch("ol_openedx_chat_xblock.block.requests.post")
    def test_ol_chat_successful_request(self, mock_post):
        """Test successful ol_chat request."""
        # Setup
        request_mock = Mock()
        request_mock.json = {"message": "Hello AI"}
        test_cookies = {
            CHAT_XBLOCK_THREAD_ID: "test_thread_id",
            CHAT_XBLOCK_BLOCK_ID: self.xblock.usage_key.block_id,
        }
        request_mock.cookies = Mock()
        request_mock.cookies.get.side_effect = lambda key, default=None: {
            COOKIE_NAME_CHAT_XBLOCK: json.dumps(test_cookies),
        }.get(key, default)

        # Mock response
        mock_response = Mock()
        mock_response.content = b'{"response": "Hello human"}'
        mock_response.cookies = Mock()
        mock_response.cookies.get.return_value = "new_thread_id"
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        response = self.xblock.ol_chat(request_mock)

        assert isinstance(response, Response)
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"]["message"] == "Hello AI"
        assert call_args[1]["json"]["course_id"] == "test_course_123"
        assert call_args[1]["cookies"][COOKIE_NAME_SYLLABUS_ANON] == "test_thread_id"

    @patch("ol_openedx_chat_xblock.block.requests.post")
    def test_ol_chat_different_block_id_resets_session(self, mock_post):
        """Test that different block_id resets the session."""
        request_mock = Mock()
        test_cookies = {
            CHAT_XBLOCK_THREAD_ID: "test_thread_id",
            CHAT_XBLOCK_BLOCK_ID: "different_block_id",
        }

        request_mock.json = {"message": "Hello AI"}
        request_mock.cookies = Mock()
        request_mock.cookies.get.side_effect = lambda key, default=None: {
            COOKIE_NAME_CHAT_XBLOCK: json.dumps(test_cookies),
        }.get(key, default)

        # Mock response
        mock_response = Mock()
        mock_response.content = b'{"response": "Hello human"}'
        mock_response.cookies = Mock()
        mock_response.cookies.get.return_value = "new_thread_id"
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        self.xblock.ol_chat(request_mock)

        # Verify that session was reset (None sent instead of old_thread_id)
        call_args = mock_post.call_args
        assert call_args[1]["cookies"][COOKIE_NAME_SYLLABUS_ANON] is None

    @data(
        (
            requests.exceptions.RequestException("Network error"),
            api_status.HTTP_400_BAD_REQUEST,
            b"Something went wrong while contacting the AI service",
        ),
        (
            Exception("Unexpected error"),
            api_status.HTTP_500_INTERNAL_SERVER_ERROR,
            b"An unexpected error occurred",
        ),
    )
    @unpack
    @patch("ol_openedx_chat_xblock.block.requests.post")
    def test_ol_chat_exceptions(
        self, exception, expected_status, expected_message, mock_post
    ):
        """Test ol_chat with various exceptions."""
        request_mock = Mock()
        test_cookies = {
            CHAT_XBLOCK_THREAD_ID: "test_thread_id",
            CHAT_XBLOCK_BLOCK_ID: "different_block_id",
        }
        request_mock.json = {"message": "Hello AI"}
        request_mock.cookies = Mock()
        request_mock.cookies.get.side_effect = lambda key, default=None: {
            COOKIE_NAME_CHAT_XBLOCK: json.dumps(test_cookies),
        }.get(key, default)

        mock_post.side_effect = exception

        response = self.xblock.ol_chat(request_mock)

        assert isinstance(response, Response)
        assert response.status_int == expected_status
        assert expected_message in response.body

    @patch("ol_openedx_chat_xblock.block.pkg_resources.resource_string")
    def test_get_resource_bytes(self, mock_resource_string):
        """Test get_resource_bytes function."""
        mock_resource_string.return_value = b"test content"

        result = get_resource_bytes("test/path")

        assert result == "test content"
        mock_resource_string.assert_called_once()

    @patch("ol_openedx_chat_xblock.block.get_resource_bytes")
    def test_render_template(self, mock_get_resource_bytes):
        """Test render_template function."""
        mock_get_resource_bytes.return_value = "Hello {{ name }}!"

        result = render_template("test/template.html", {"name": "World"})

        assert result == "Hello World!"

    def test_get_xblock_chat_url(self):
        """
        Test that get_xblock_chat_url returns the tutor chat API URL when
        is_tutor_xblock is True.
        """
        for xblock_type in [XBLOCK_TYPE_TUTOR, XBLOCK_TYPE_SYLLABUS]:
            self.xblock.is_tutor_xblock = xblock_type == XBLOCK_TYPE_TUTOR
            with patch("ol_openedx_chat_xblock.block.settings") as settings:
                assert (
                    self.xblock.get_xblock_chat_url()
                    == settings.MIT_LEARN_AI_XBLOCK_CHAT_API_URL
                    if xblock_type == XBLOCK_TYPE_SYLLABUS
                    else settings.MIT_LEARN_AI_XBLOCK_TUTOR_CHAT_API_URL
                )

    def test_get_xblock_state(self):
        """Test that get_xblock_state returns the correct state based on
        is_tutor_xblock.
        """
        self.xblock.is_tutor_xblock = True
        assert self.xblock.get_xblock_state() == XBLOCK_TYPE_TUTOR
        self.xblock.is_tutor_xblock = False
        assert self.xblock.get_xblock_state() == XBLOCK_TYPE_SYLLABUS

    @patch("ol_openedx_chat_xblock.block.tracker.emit")
    def test_send_tracker_event(self, mock_emit):
        """Test that send_tracker_event calls the tracker emit function with the
        correct arguments."""
        self.xblock.is_tutor_xblock = False
        self.xblock.course_id = "course_id"
        self.xblock.send_tracker_event("event", "value", "pset")
        mock_emit.assert_called_once()
        args, kwargs = mock_emit.call_args
        assert "event" in args[0]
        assert args[1]["canvas_course_id"] == "course_id"
        assert args[1]["problem_set"] == "pset"

    def test_get_ai_chat_init_js_args_syllabus(self):
        """Test that get_ai_chat_init_js_args returns the correct arguments for
        syllabus.
        """
        self.xblock.is_tutor_xblock = False
        args = self.xblock.get_ai_chat_init_js_args()
        assert args["block_id"] == "test123"
        assert "ask_tim_title" in args
        assert "bot_initial_message" in args

    def test_get_ai_chat_init_js_args_tutor(self):
        """Test that get_ai_chat_init_js_args returns the correct arguments for
        tutor.
        """
        self.xblock.is_tutor_xblock = True
        with patch.object(self.xblock, "get_problem_set_url", return_value="pset_url"):
            args = self.xblock.get_ai_chat_init_js_args()
            assert args["problem_list_url"] == "pset_url"
            assert "problem_set_initial_message" in args

    def test_get_chat_thread_cookie_name(self):
        """Test that get_chat_thread_cookie_name returns the correct cookie name based
        on is_tutor_xblock.
        """
        self.xblock.is_tutor_xblock = True
        assert self.xblock.get_chat_thread_cookie_name() == COOKIE_NAME_TUTOR_ANON
        self.xblock.is_tutor_xblock = False
        assert self.xblock.get_chat_thread_cookie_name() == COOKIE_NAME_SYLLABUS_ANON

    @data(
        (
            {
                "course_id": "",
                "learn_readable_course_id": "",
                "message": "msg",
                "problem_set": "pset",
                "is_tutor": False,
            },
            "Course ID is required.",
        ),
        (
            {
                "course_id": "cid",
                "learn_readable_course_id": "auto_id",
                "message": "",
                "problem_set": "pset",
                "is_tutor": False,
            },
            "Message field is required.",
        ),
        (
            {
                "course_id": "cid",
                "learn_readable_course_id": "auto_id",
                "message": "msg",
                "problem_set": "",
                "is_tutor": True,
            },
            "Problem set title is required.",
        ),
        (
            {
                "course_id": "cid",
                "learn_readable_course_id": "auto_id",
                "message": "msg",
                "problem_set": "pset",
                "is_tutor": False,
            },
            None,
        ),
    )
    @unpack
    def test_validate_required_api_params(self, params, expected_error):
        """Test validate_required_api_params with various parameter combinations."""
        self.xblock.learn_readable_course_id = params["learn_readable_course_id"]
        self.xblock.is_tutor_xblock = params["is_tutor"]

        error = self.xblock.validate_required_api_params(
            params["course_id"], params["message"], params["problem_set"]
        )

        assert error == expected_error

    @patch("ol_openedx_chat_xblock.block.get_current_request")
    def test_generate_canvas_course_id_success(self, mock_get_req):
        """Test that generate_canvas_course_id returns the correct course ID."""
        mock_req = Mock()
        mock_req.GET.dict.return_value = {"custom_course_id": "cid"}
        mock_req.POST.dict.return_value = {"context_label": "label"}
        mock_get_req.return_value = mock_req
        result = generate_canvas_course_id()
        assert result == "cid-label"

    @patch("ol_openedx_chat_xblock.block.get_current_request")
    def test_generate_canvas_course_id_missing_request(self, mock_get_req):
        """Test that generate_canvas_course_id returns an empty string when the request
        is missing."""
        mock_get_req.return_value = None
        assert generate_canvas_course_id() == ""

    @patch("ol_openedx_chat_xblock.block.get_current_request")
    def test_generate_canvas_course_id_missing_param(self, mock_get_req):
        """Test that generate_canvas_course_id returns an empty string when the required
        parameters are missing."""
        mock_req = Mock()
        mock_req.GET.dict.return_value = {}
        mock_req.POST.dict.return_value = {}
        mock_get_req.return_value = mock_req
        assert generate_canvas_course_id() == ""

    @data(
        (
            "test_course_123",
            "",
            "http://test.com/list/",
            "http://test.com/list/?run_readable_id=test_course_123%2Bcanvas",
        ),
        (
            "test_course_123",
            "",
            "http://test.com/list",
            "http://test.com/list/?run_readable_id=test_course_123%2Bcanvas",
        ),
        (
            "",
            "canvas_course_123",
            "http://test.com/list/",
            "http://test.com/list/?run_readable_id=canvas_course_123%2Bcanvas",
        ),
        (
            "priority_course_123",
            "fallback_course_456",
            "http://test.com/list/",
            "http://test.com/list/?run_readable_id=priority_course_123%2Bcanvas",
        ),
    )
    @unpack
    def test_get_problem_set_url(
        self, course_id, learn_readable_course_id, base_url, expected
    ):
        """Test that get_problem_set_url returns the correct URL."""
        self.xblock.course_id = course_id
        self.xblock.learn_readable_course_id = learn_readable_course_id

        with patch("ol_openedx_chat_xblock.block.settings") as mock_settings:
            mock_settings.MIT_LEARN_AI_XBLOCK_PROBLEM_SET_LIST_URL = base_url
            url = self.xblock.get_problem_set_url()
            assert url == expected
