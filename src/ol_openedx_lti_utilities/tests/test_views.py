from unittest.mock import Mock, patch

from ddt import ddt
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


@ddt
class TestLtiUserFixView(TestCase):
    """Test cases for LtiUserFixView."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.url = "/api/lti-user-fix/"  # Use direct URL path instead of reverse
        self.valid_email = "test@example.com"

        # Create and authenticate a staff user for API access
        self.user = User.objects.create_user(
            username="testuser_auth",
            email="testauth@example.com",
            password="testpass123",  # pragma: allowlist secret  # noqa: S106
            is_staff=True,
        )
        self.client.force_authenticate(user=self.user)

    @patch("ol_openedx_lti_utilities.views.LtiUser")
    @patch(
        "ol_openedx_lti_utilities.views.create_retirement_request_and_deactivate_account"
    )
    @patch("ol_openedx_lti_utilities.views.UserSocialAuth.objects")
    def test_successful_lti_user_fix(
        self, mock_user_social_auth_objects, mock_retirement_user, mock_lti_user_model
    ):
        """Test successful LTI user fix."""
        # Mock LTI user with bad username
        mock_lti_user = Mock()
        mock_lti_user.lti_user_id = "TEST_LTI_USER_ID"

        mock_edx_user = Mock()
        mock_edx_user.username = "TEST_LTI_USER_ID"
        mock_edx_user.email = self.valid_email
        mock_lti_user.edx_user = mock_edx_user

        mock_qs = Mock()
        mock_qs.first.return_value = mock_lti_user
        mock_lti_user_model.objects.filter.return_value = mock_qs

        payload = {"email": self.valid_email}

        response = self.client.post(self.url, payload)
        mock_edx_user.save.assert_called_once()
        mock_retirement_user.assert_called_once_with(mock_edx_user)
        mock_qs = mock_user_social_auth_objects.filter.return_value
        mock_user_social_auth_objects.filter.return_value.delete.assert_called_once()

        assert response.status_code == status.HTTP_200_OK

    def test_missing_required_fields(self):
        """Test request with missing required fields."""
        response = self.client.post(self.url, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email is required" in response.content.decode()

    @patch("ol_openedx_lti_utilities.views.LtiUser")
    def test_no_lti_user_found(self, mock_lti_user_model):
        """Test when no LTI user exists for given email."""
        mock_qs = Mock()
        mock_qs.first.return_value = None
        mock_lti_user_model.objects.filter.return_value = mock_qs

        payload = {"email": self.valid_email}

        response = self.client.post(self.url, payload)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("ol_openedx_lti_utilities.views.LtiUser")
    def test_user_does_not_need_fixing(self, mock_lti_user_model):
        """Test when LTI user has normal username (doesn't need fixing)."""
        # Mock LTI user with normal username
        mock_edx_user = Mock()
        mock_edx_user.username = "normalusername"
        mock_edx_user.email = self.valid_email

        mock_lti_user = Mock()
        mock_lti_user.edx_user = mock_edx_user

        mock_qs = Mock()
        mock_qs.exists.return_value = True
        mock_qs.first.return_value = mock_lti_user
        mock_lti_user_model.objects.filter.return_value = mock_qs

        payload = {"email": self.valid_email}

        response = self.client.post(self.url, payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            "User with the given email does not appear to be an LTI-created user."
            in response.content.decode()
        )

    def test_only_post_method_allowed(self):
        """Test that only POST method is allowed."""
        payload = {"email": self.valid_email}

        # Test GET
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        # Test PUT
        response = self.client.put(self.url, payload)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        # Test DELETE
        response = self.client.delete(self.url)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        # Test PATCH
        response = self.client.patch(self.url, payload)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    @patch("ol_openedx_lti_utilities.views.log")
    @patch("ol_openedx_lti_utilities.views.LtiUser")
    def test_logging_on_missing_fields(self, mock_lti_user_model, mock_log):  # noqa: ARG002
        """Test that error is logged when required fields are missing."""
        payload = {}

        response = self.client.post(self.url, payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        mock_log.error.assert_called_once_with("email is required")

    @patch("ol_openedx_lti_utilities.views.log")
    @patch("ol_openedx_lti_utilities.views.LtiUser")
    def test_logging_on_no_user_found(self, mock_lti_user_model, mock_log):
        """Test that error is logged when no LTI user is found."""
        mock_qs = Mock()
        mock_qs.first.return_value = None
        mock_lti_user_model.objects.filter.return_value = mock_qs

        payload = {"email": self.valid_email}

        response = self.client.post(self.url, payload)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        mock_log.error.assert_called_once_with(
            "No user was found against the given email (%s)", self.valid_email
        )
