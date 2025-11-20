"""
Views for LTI Utilities operations.
"""

import logging

from django.db import transaction
from django.http import Http404, HttpResponseBadRequest
from edx_rest_framework_extensions import permissions
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from edx_rest_framework_extensions.auth.session.authentication import (
    SessionAuthenticationAllowInactiveUser,
)
from lms.djangoapps.lti_provider.models import LtiUser
from openedx.core.djangoapps.user_api.accounts.utils import (
    create_retirement_request_and_deactivate_account,
)
from openedx.core.lib.api.authentication import BearerAuthenticationAllowInactiveUser
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from social_django.models import UserSocialAuth

log = logging.getLogger(__name__)


PLACEHOLDER_EMAIL_DOMAIN = "lti_example.com"


class LtiUserFixView(APIView):
    """
    Fix the auth record of an LTI-created user.

    POST /api/lti-user-fix/

    Request payload:
    {
        "email": "<user_email>",
    }

    Responses:
    - 200: Fixed successfully
    - 400: Bad request or user does not need fixing
    - 404: No matching LTI user found
    """

    # Same authentication model as CourseModesMixin
    authentication_classes = (
        JwtAuthentication,
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )

    # Same permission enforcement as CourseModesMixin
    permission_classes = (permissions.JWT_RESTRICTED_APPLICATION_OR_USER_ACCESS,)

    # Only POST allowed
    http_method_names = ["post"]

    def post(self, request):
        """
        Handle POST request to fix LTI user authentication record.

        This endpoint fixes LTI-created users who have lti_user_id as usernames

        Parameters
        ----------
        request : Request
            The HTTP request object containing email in the payload.

        Returns
        -------
        Response
            HTTP 200 on successful fix, HTTP 400 for bad requests or users that
            don't need fixing, HTTP 404 if no matching LTI user is found

        Raises
        ------
        Http404
            If no LTI user exists for the provided email address
        """
        user_email = request.data.get("email")

        if not user_email:
            log.error("email is required")
            return HttpResponseBadRequest("email is required")

        # A user that is created by LTI will always have the same username as
        # lti_user_id in LtiUser table.
        with transaction.atomic():
            lti_user = LtiUser.objects.filter(edx_user__email=user_email).first()
            if not lti_user:
                log.error("No user was found against the given email (%s)", user_email)
                raise Http404
            if lti_user.lti_user_id != lti_user.edx_user.username:
                log.error(
                    "User with email (%s) does not appear to be an LTI-created user",
                    user_email,
                )
                return HttpResponseBadRequest(
                    "User with the given email does not appear to be an "
                    "LTI-created user."
                )

            user = lti_user.edx_user
            user.email = user.email.split("@")[0] + "@" + PLACEHOLDER_EMAIL_DOMAIN
            user.save()
            # Remove social auth records for this user
            UserSocialAuth.objects.filter(user=user).delete()
            # Remove the old LTI mapping so that a new one gets created the next time
            # users access edX via LTI
            lti_user.delete()

        # Send the user for retirement and deactivate the account
        try:
            create_retirement_request_and_deactivate_account(user)
        except Exception as e:  # noqa: BLE001
            log.error("Error retiring and deactivating user: %s", e)  # noqa: TRY400

        return Response(status=status.HTTP_200_OK)
