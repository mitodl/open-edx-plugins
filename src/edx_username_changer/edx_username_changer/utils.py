"""
Utility methods for edx-username-changer plugin
"""

from common.djangoapps.student.models import (
    CourseEnrollment,
)
from django.contrib.auth import get_user_model
from django.db import transaction
from social_django.models import UserSocialAuth

User = get_user_model()


def update_user_social_auth_uid(old_username, new_username):
    """
    Change uid in django-social-auth for OAuth based user accounts
    iff uid is based on username otherwise it doesn't make any effect
    """
    with transaction.atomic():
        UserSocialAuth.objects.filter(uid=old_username).update(uid=new_username)


def get_enrolled_course_ids(user):
    """
    Return course ids of all the active enrollments of the provided user
    """
    return [
        str(enrollment.course_id)
        for enrollment in CourseEnrollment.enrollments_for_user(user)
    ]
