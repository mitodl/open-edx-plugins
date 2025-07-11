import logging

from social_core.exceptions import AuthAlreadyAssociated

log = logging.getLogger()


def debug_social_user(backend, uid, user=None, *args, **kwargs):  # noqa: ARG001
    """Run a debug version of social_core.pipeline.social_auth.social_user"""
    provider = backend.name
    social = backend.strategy.storage.user.get_social_auth(provider, uid)

    if social:
        if user and social.user != user:
            log.info(
                (
                    "Auth already associated: "
                    "provider=%s uid=%s social_user=%s pipeline_user=%s"
                ),
                provider,
                uid,
                social.user.username,
                user.username,
            )
            raise AuthAlreadyAssociated(backend)

        if not user:
            user = social.user

    return {
        "social": social,
        "user": user,
        "is_new": user is None,
        "new_association": social is None,
    }
