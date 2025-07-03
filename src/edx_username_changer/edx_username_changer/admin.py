"""
Django admin pages for edx-username-changer plugin
"""

import contextlib

from common.djangoapps.student.admin import (
    UserAdmin as BaseUserAdmin,
)
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth import get_user_model

User = get_user_model()


class UserAdmin(BaseUserAdmin):
    """
    Admin interface for the User model.
    """

    def get_readonly_fields(self, request, obj=None):
        """
        Remove 'username' from the read-only fields
        to make it editable through the admin panel
        """
        readonly_fields = super().get_readonly_fields(request, obj)
        if settings.FEATURES.get("ENABLE_EDX_USERNAME_CHANGER") and obj:
            return tuple([name for name in readonly_fields if name != "username"])
        return readonly_fields


# We must first un-register the User model since it was registered by edX's core code.
with contextlib.suppress(NotRegistered):
    admin.site.unregister(User)

admin.site.register(User, UserAdmin)
