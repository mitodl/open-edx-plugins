"""
This file contains celery tasks related to edx_username_changer plugin.
"""

from django.contrib.auth import get_user_model

User = get_user_model()

# Forum username updates are no longer needed with Forum v2.
# Forum v2 stores data in Django models and usernames are updated
# automatically through Django's ORM when the User model changes.
