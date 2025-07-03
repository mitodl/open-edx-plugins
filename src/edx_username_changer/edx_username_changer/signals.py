"""
Signals and Signal Handlers for edx-username-changer plugin
"""

from common.djangoapps.util.model_utils import (  # pylint: disable=import-error
    get_changed_fields_dict,
)
from django.conf import settings
from django.db import transaction

from edx_username_changer.tasks import task_update_username_in_forum
from edx_username_changer.utils import update_user_social_auth_uid


def user_pre_save_callback(sender, **kwargs):
    """
    Pre-save signal handler of User model to store changed fields to be used later
    """
    if settings.FEATURES.get("ENABLE_EDX_USERNAME_CHANGER"):
        user = kwargs["instance"]
        fields_to_update = get_changed_fields_dict(user, sender)
        if "username" in fields_to_update:
            fields_to_update.update({"new_username": user.username})
            user._updated_fields = fields_to_update  # noqa: SLF001


def user_post_save_callback(sender, **kwargs):  # noqa: ARG001
    """
    Post-save signal handler of User model to update username throughout the application
    """
    if settings.FEATURES.get("ENABLE_EDX_USERNAME_CHANGER"):
        user = kwargs["instance"]
        if (
            hasattr(user, "_updated_fields")
            and user._updated_fields  # noqa: SLF001
            and {"username", "new_username"}.issubset(user._updated_fields)  # noqa: SLF001
        ):
            new_username = user._updated_fields["new_username"]  # noqa: SLF001
            transaction.on_commit(
                lambda: task_update_username_in_forum.delay(new_username)
            )
            update_user_social_auth_uid(user._updated_fields["username"], new_username)  # noqa: SLF001
            delattr(user, "_updated_fields")
