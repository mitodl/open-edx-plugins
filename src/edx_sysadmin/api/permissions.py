"""
Custom Permissions for edx-sysadmin API Views
"""

import hmac
import logging
from hashlib import sha1, sha256

from django.conf import settings
from django.utils.encoding import force_bytes
from django.utils.translation import gettext as _
from rest_framework import permissions, status
from rest_framework.exceptions import APIException

logger = logging.getLogger(__name__)


class GithubWebhookPermissionException(APIException):
    """
    API Exception for github webhook request
    """

    status_code = status.HTTP_403_FORBIDDEN
    default_code = _("not_authenticated")


class GithubWebhookPermission(permissions.BasePermission):
    """
    Validates Github webhook request permissions
    :returns boolean: True if permission is valid else False
    """

    def has_permission(self, request, view):  # noqa: ARG002
        def _validate_github_webhook_signature(request):
            """
            Validate Github webhook request signature
            :returns boolean: True if HMAC matches else False
            :returns str: Error messages
            """
            if (
                not hasattr(settings, "SYSADMIN_GITHUB_WEBHOOK_KEY")
                or settings.SYSADMIN_GITHUB_WEBHOOK_KEY is None
            ):
                return (
                    False,
                    _("SYSADMIN_GITHUB_WEBHOOK_KEY is not configured in settings"),
                )

            header_signature = request.headers.get(
                "X-Hub-Signature-256"
            ) or request.headers.get("X-Hub-Signature")
            if header_signature is None:
                return False, _(
                    "X-Hub-Signature-256 or sha1 not found in request headers"
                )

            sha_name, signature = header_signature.split("=")
            if sha_name not in ["sha256", "sha1"]:
                return False, _("Signature is not using sha256 or sha1")

            mac = hmac.new(
                force_bytes(settings.SYSADMIN_GITHUB_WEBHOOK_KEY),
                msg=force_bytes(request.body),
                digestmod=sha256 if sha_name == "sha256" else sha1,
            )
            if not hmac.compare_digest(
                force_bytes(mac.hexdigest()), force_bytes(signature)
            ):
                return False, _("Signatures didn't match")

            return True, ""

        is_valid, err_msg = _validate_github_webhook_signature(request)

        if not is_valid:
            logger.exception(f"{self.__class__.__name__}:: {err_msg}")  # noqa: G004
            raise GithubWebhookPermissionException(detail=err_msg)

        return is_valid
