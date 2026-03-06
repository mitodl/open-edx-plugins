"""
Tests for Permissions
"""

from unittest.mock import patch

import ddt
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status as _status
from rest_framework.test import APIClient

SYSADMIN_GITHUB_WEBHOOK_KEY = (
    "nuiVypAArY7lFDgMdyC5kwutDGQdDc6rXljuIcI5iBttpPebui"  # pragma: allowlist secret
)


@ddt.ddt
class GitReloadAPIViewTestCase(TestCase):
    """
    Test Case for GithubWebhookPermission permission
    """

    def setUp(self):
        super().setUp()
        self.client = APIClient()

    @override_settings(SYSADMIN_GITHUB_WEBHOOK_KEY=SYSADMIN_GITHUB_WEBHOOK_KEY)
    @override_settings(SYSADMIN_DEFAULT_BRANCH="master")
    @ddt.data(
        (
            "d3a2424a1ad48d8441712400fd75392d56707a7b3e1dc4869239d87ee381cfa9",  # pragma: allowlist secret  # noqa: E501
            "refs/heads/master",
            "push",
            "edx4edx_lite",
            "git@github.com:edx/edx4edx_lite.git",
            _status.HTTP_200_OK,
        ),
        (
            "dd930da0a34996332e8c983aaeeb9e1cca45cc9b92492f47774d351de4740ddc",  # pragma: allowlist secret  # noqa: E501
            "refs/heads/master",
            "push",
            "edx4edx_lite",
            "git@github.com:edx/edx4edx_lite.git",
            _status.HTTP_403_FORBIDDEN,
        ),
        (
            "98f48c1b0d35ceec2bfc420f96b76e500b538a6484b17c83c5df4d2c556d8c86",  # pragma: allowlist secret  # noqa: E501
            "refs/heads/dev",
            "push",
            "edx4edx_lite",
            "git@github.com:edx/edx4edx_lite.git",
            _status.HTTP_400_BAD_REQUEST,
        ),
        (
            "d3a2424a1ad48d8441712400fd75392d56707a7b3e1dc4869239d87ee381cfa9",  # pragma: allowlist secret  # noqa: E501
            "refs/heads/master",
            "review",
            "edx4edx_lite",
            "git@github.com:edx/edx4edx_lite.git",
            _status.HTTP_400_BAD_REQUEST,
        ),
        (
            "e9b59c215df414f6ba45508912ce6beeb089bdab22ee3fd2e79ebdf42fe2e481",  # pragma: allowlist secret  # noqa: E501
            "refs/heads/master",
            "push",
            "",
            "git@github.com:edx/edx4edx_lite.git",
            _status.HTTP_400_BAD_REQUEST,
        ),
        (
            "319566e23382c5823ac3483acece8a80644574cf4b35015acd6dc5a82d6ee8b7",  # pragma: allowlist secret  # noqa: E501
            "refs/heads/master",
            "push",
            "edx4edx_lite",
            "",
            _status.HTTP_400_BAD_REQUEST,
        ),
    )
    @ddt.unpack
    def test_git_reload_apiview(  # noqa: PLR0913
        self,
        signature,
        git_ref,
        event,
        repo_name,
        ssh_url,
        status,
    ):
        """
        Test GitReloadAPIView with Signature and Payload
        """
        payload = {
            "repository": {
                "ssh_url": ssh_url,
                "name": repo_name,
            },
            "ref": git_ref,
        }
        response = self.client.post(
            reverse("sysadmin:api:git-reload"),
            payload,
            format="json",
            headers={
                "x-hub-signature-256": f"sha256={signature}",
                "x-github-event": event,
            },
        )

        assert response.status_code == status

    @override_settings(SYSADMIN_GITHUB_WEBHOOK_KEY=SYSADMIN_GITHUB_WEBHOOK_KEY)
    @override_settings(SYSADMIN_DEFAULT_BRANCH="master")
    @ddt.data(
        (
            "d3a2424a1ad48d8441712400fd75392d56707a7b3e1dc4869239d87ee381cfa9",  # pragma: allowlist secret  # noqa: E501
            "refs/heads/master",
            "push",
            "edx4edx_lite",
            "git@github.com:edx/edx4edx_lite.git",
            _status.HTTP_200_OK,
        ),
        (
            "d5bd1308cac89ce747cfc93a2679429aa06e179279d912094bac7901e281b783",  # pragma: allowlist secret  # noqa: E501
            "refs/heads/dummy-test-branch",
            "push",
            "edx4edx_lite",
            "git@github.com:edx/edx4edx_lite.git",
            _status.HTTP_400_BAD_REQUEST,
        ),
        (
            "319566e23382c5823ac3483acece8a80644574cf4b35015acd6dc5a82d6ee8b7",  # pragma: allowlist secret  # noqa: E501
            "refs/heads/master",
            "push",
            "edx4edx_lite",
            "",
            _status.HTTP_400_BAD_REQUEST,
        ),
    )
    @ddt.unpack
    def test_git_reload_api_view_no_repo(  # noqa: PLR0913
        self,
        signature,
        git_ref,
        event,
        repo_name,
        ssh_url,
        status,
    ):
        """
        Test GitReloadAPIView with Signature and Payload
        """
        payload = {
            "repository": {
                "ssh_url": ssh_url,
                "name": repo_name,
            },
            "ref": git_ref,
        }
        with (
            patch(
                "edx_sysadmin.api.views.get_local_course_repo"
            ) as mocked_get_local_course_repo,
            patch("edx_sysadmin.api.views.add_repo") as mocked_add_repo,
            patch(
                "edx_sysadmin.api.views.get_local_active_branch", return_value=git_ref
            ),
        ):
            response = self.client.post(
                reverse("sysadmin:api:git-reload"),
                payload,
                format="json",
                headers={
                    "x-hub-signature-256": f"sha256={signature}",
                    "x-github-event": event,
                },
            )

            assert response.status_code == status
            if git_ref == "refs/heads/master" and ssh_url:
                mocked_get_local_course_repo.assert_called_once_with(repo_name)

            if response.status_code == _status.HTTP_200_OK:
                mocked_add_repo.delay.assert_called()

    # Should return a bad request when "SYSADMIN_DEFAULT_BRANCH" is not configured
    @override_settings(SYSADMIN_GITHUB_WEBHOOK_KEY=SYSADMIN_GITHUB_WEBHOOK_KEY)
    @ddt.data(
        (
            "d3a2424a1ad48d8441712400fd75392d56707a7b3e1dc4869239d87ee381cfa9",  # pragma: allowlist secret  # noqa: E501
            "refs/heads/master",
            "push",
            "edx4edx_lite",
            "git@github.com:edx/edx4edx_lite.git",
            _status.HTTP_400_BAD_REQUEST,
        ),
    )
    @ddt.unpack
    def test_git_reload_api_view_no_repo_default_branch(  # noqa: PLR0913
        self,
        signature,
        git_ref,
        event,
        repo_name,
        ssh_url,
        status,
    ):
        """
        Test GitReloadAPIView with Signature and Payload
        """
        payload = {
            "repository": {
                "ssh_url": ssh_url,
                "name": repo_name,
            },
            "ref": git_ref,
        }
        response = self.client.post(
            reverse("sysadmin:api:git-reload"),
            payload,
            format="json",
            headers={
                "x-hub-signature-256": f"sha256={signature}",
                "x-github-event": event,
            },
        )
        assert response.status_code == status

    @override_settings(SYSADMIN_GITHUB_WEBHOOK_KEY=SYSADMIN_GITHUB_WEBHOOK_KEY)
    @override_settings(SYSADMIN_DEFAULT_BRANCH="master")
    @ddt.data(
        (
            "d3a2424a1ad48d8441712400fd75392d56707a7b3e1dc4869239d87ee381cfa9",  # pragma: allowlist secret  # noqa: E501
            "refs/heads/master",
            "refs/heads/live",
            "push",
            "edx4edx_lite",
            "git@github.com:edx/edx4edx_lite.git",
            _status.HTTP_200_OK,
        ),
        (
            "d3a2424a1ad48d8441712400fd75392d56707a7b3e1dc4869239d87ee381cfa9",  # pragma: allowlist secret  # noqa: E501
            "refs/heads/master",
            "refs/heads/staging",
            "push",
            "edx4edx_lite",
            "git@github.com:edx/edx4edx_lite.git",
            _status.HTTP_200_OK,
        ),
    )
    @ddt.unpack
    def test_git_reload_api_view_different_active_branch(  # noqa: PLR0913
        self,
        signature,
        git_ref,
        active_branch,
        event,
        repo_name,
        ssh_url,
        status,
    ):
        """
        Test GitReloadAPIView when local repo's active branch is different
        from pushed branch. This should trigger checkout to the settings
        default branch and then reload.
        """
        payload = {
            "repository": {
                "ssh_url": ssh_url,
                "name": repo_name,
            },
            "ref": git_ref,
        }
        with (
            patch(
                "edx_sysadmin.api.views.get_local_course_repo", return_value="mock_repo"
            ) as mocked_get_local_course_repo,
            patch("edx_sysadmin.api.views.add_repo") as mocked_add_repo,
            patch(
                "edx_sysadmin.api.views.get_local_active_branch",
                return_value=active_branch,
            ) as mocked_get_local_active_branch,
        ):
            response = self.client.post(
                reverse("sysadmin:api:git-reload"),
                payload,
                format="json",
                headers={
                    "x-hub-signature-256": f"sha256={signature}",
                    "x-github-event": event,
                },
            )

            assert response.status_code == status
            mocked_get_local_course_repo.assert_called_once_with(repo_name)
            mocked_get_local_active_branch.assert_called_once_with("mock_repo")

            # Verify add_repo was called with ssh_url and default branch for checkout
            mocked_add_repo.delay.assert_called_once_with(repo=ssh_url, branch="master")

            # Verify the response message indicates checkout is happening
            assert "Active branch" in response.data["message"]
            assert "different" in response.data["message"]

    @override_settings(SYSADMIN_GITHUB_WEBHOOK_KEY=SYSADMIN_GITHUB_WEBHOOK_KEY)
    @override_settings(SYSADMIN_DEFAULT_BRANCH="master")
    @ddt.data(
        (
            "d3a2424a1ad48d8441712400fd75392d56707a7b3e1dc4869239d87ee381cfa9",  # pragma: allowlist secret  # noqa: E501
            "refs/heads/master",
            "push",
            "edx4edx_lite",
            "git@github.com:edx/edx4edx_lite.git",
            _status.HTTP_200_OK,
        ),
    )
    @ddt.unpack
    def test_git_reload_api_view_matching_active_branch(  # noqa: PLR0913
        self,
        signature,
        git_ref,
        event,
        repo_name,
        ssh_url,
        status,
    ):
        """
        Test GitReloadAPIView when local repo's active branch matches the pushed branch.
        This should trigger a normal reload without checkout.
        """
        payload = {
            "repository": {
                "ssh_url": ssh_url,
                "name": repo_name,
            },
            "ref": git_ref,
        }
        with (
            patch(
                "edx_sysadmin.api.views.get_local_course_repo", return_value="mock_repo"
            ) as mocked_get_local_course_repo,
            patch("edx_sysadmin.api.views.add_repo") as mocked_add_repo,
            patch(
                "edx_sysadmin.api.views.get_local_active_branch",
                return_value=git_ref,
            ) as mocked_get_local_active_branch,
        ):
            response = self.client.post(
                reverse("sysadmin:api:git-reload"),
                payload,
                format="json",
                headers={
                    "x-hub-signature-256": f"sha256={signature}",
                    "x-github-event": event,
                },
            )

            assert response.status_code == status
            mocked_get_local_course_repo.assert_called_once_with(repo_name)
            mocked_get_local_active_branch.assert_called_once_with("mock_repo")

            # Verify add_repo was called with just ssh_url
            mocked_add_repo.delay.assert_called_once_with(ssh_url)

            # Verify the response message indicates normal reload
            assert "Triggered reloading branch" in response.data["message"]

    @override_settings(SYSADMIN_GITHUB_WEBHOOK_KEY=SYSADMIN_GITHUB_WEBHOOK_KEY)
    @override_settings(SYSADMIN_DEFAULT_BRANCH="master")
    @ddt.data(
        (
            "d3a2424a1ad48d8441712400fd75392d56707a7b3e1dc4869239d87ee381cfa9",  # pragma: allowlist secret  # noqa: E501
            "refs/heads/master",
            "push",
            "edx4edx_lite",
            "git@github.com:edx/edx4edx_lite.git",
            _status.HTTP_400_BAD_REQUEST,
        ),
    )
    @ddt.unpack
    def test_git_reload_api_view_no_active_branch(  # noqa: PLR0913
        self,
        signature,
        git_ref,
        event,
        repo_name,
        ssh_url,
        status,
    ):
        """
        Test GitReloadAPIView when active branch cannot be determined.
        This should return an error.
        """
        payload = {
            "repository": {
                "ssh_url": ssh_url,
                "name": repo_name,
            },
            "ref": git_ref,
        }
        with (
            patch(
                "edx_sysadmin.api.views.get_local_course_repo", return_value="mock_repo"
            ) as mocked_get_local_course_repo,
            patch("edx_sysadmin.api.views.add_repo") as mocked_add_repo,
            patch(
                "edx_sysadmin.api.views.get_local_active_branch",
                return_value=None,
            ) as mocked_get_local_active_branch,
        ):
            response = self.client.post(
                reverse("sysadmin:api:git-reload"),
                payload,
                format="json",
                headers={
                    "x-hub-signature-256": f"sha256={signature}",
                    "x-github-event": event,
                },
            )

            assert response.status_code == status
            mocked_get_local_course_repo.assert_called_once_with(repo_name)
            mocked_get_local_active_branch.assert_called_once_with("mock_repo")

            # Verify add_repo was NOT called
            mocked_add_repo.delay.assert_not_called()

            # Verify error message about unable to determine active branch
            assert "Couldn't determine the active branch" in response.data["message"]
