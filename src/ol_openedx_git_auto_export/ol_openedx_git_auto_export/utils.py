"""
Utility functions for the ol_openedx_git_auto_export app.
"""
from django.contrib.auth.models import User


def get_publisher_username(course_module):
    """
    Returns the username of the user who published the course.
    If the user cannot be found, returns None.
    """
    if not course_module:
        return None

    user_id = getattr(course_module, "published_by", None)
    if not user_id:
        return None

    user = User.objects.filter(id=user_id).first()
    return user.username if user else None
