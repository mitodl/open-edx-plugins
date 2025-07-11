import pytest
from common.djangoapps.student.tests.factories import UserFactory
from openedx.core.djangolib.testing.utils import skip_unless_cms
from social_core.exceptions import AuthAlreadyAssociated
from social_django.models import UserSocialAuth

from ol_social_auth.actions import debug_social_user
from ol_social_auth.backends import OLOAuth2

pytestmark = pytest.mark.django_db


@skip_unless_cms
@pytest.mark.parametrize("user_exists", [True, False])
@pytest.mark.parametrize("user_matches", [True, False])
@pytest.mark.parametrize("has_social", [True, False])
def test_debug_social_user(mocker, user_exists, user_matches, has_social):
    """Test that debug_social_user works as expected"""
    backend = OLOAuth2()
    mock_log = mocker.patch("ol_social_auth.actions.log", autospec=True)

    uid = "social-uid"
    pipeline_user = UserFactory.create() if user_exists else None
    user = pipeline_user if user_matches else UserFactory.create()
    social = (
        UserSocialAuth.objects.create(uid=uid, provider=backend.name, user=user)
        if has_social
        else None
    )

    if social and not user_matches:
        with pytest.raises(AuthAlreadyAssociated):
            debug_social_user(backend=backend, uid=uid, user=pipeline_user)

        mock_log.info.assert_called_once(
            (
                "Auth already associated: "
                "provider=%s uid=%s social_user=%s "
                "pipeline_user=%s"
            ),
            backend.name,
            uid,
            social.user.username,
            user.username,
        )
    else:
        result = debug_social_user(backend=backend, uid=uid, user=pipeline_user)
        assert result == {
            "social": social,
            "user": user,
            "is_new": not user_exists,
            "new_association": social is None,
        }
