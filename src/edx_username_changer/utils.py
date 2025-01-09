"""
Utility methods for edx-username-changer plugin
"""

from common.djangoapps.student.models import (
    CourseEnrollment,
)
from django.contrib.auth import get_user_model
from django.db import transaction
from edx_username_changer.exceptions import UpdateFailedException
from openedx.core.djangoapps.django_comment_common.comment_client.comment import (
    Comment,
)
from openedx.core.djangoapps.django_comment_common.comment_client.thread import (
    Thread,
)
from openedx.core.djangoapps.django_comment_common.comment_client.utils import (
    perform_request as perform_forum_request,
)
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


def get_involved_threads(course_id, user_id):
    """
    Return an iterator of all the discussion-forum threads
    against provided user and course
    """
    page = 0
    involved_threads = []
    while len(involved_threads) > 0 or page == 0:
        involved_threads = [
            Thread.find(id=thread["id"]).retrieve(
                with_responses=True, recursive=True, mark_as_read=False
            )
            for thread in Thread.search(
                {"course_id": course_id, "user_id": user_id, "page": page}
            ).collection
        ]
        yield from involved_threads
        page += 1


def get_authored_threads_and_comments(comment_user, enrolled_course_ids):
    """
    Return an iterator of all the discussion-forum threads
    and comments of provided user and course
    """

    for course_id in enrolled_course_ids:
        involved_threads = get_involved_threads(course_id, comment_user.id)
        for thread in involved_threads:
            if thread["user_id"] == comment_user.id:
                yield thread.to_dict()

            children_to_scan = (
                thread.get("children", [])
                + thread.get("endorsed_responses", [])
                + thread.get("non_endorsed_responses", [])
            )

            while children_to_scan:
                child = children_to_scan.pop(0)
                children_to_scan.extend(child["children"])
                if child["user_id"] == comment_user.id:
                    yield child


def update_comment_user_username(comment_user, new_username):
    """
    Update username for discussion-forum comment-users via Forum APIs
    """
    user_detail_url = comment_user.url_with_id(params={"id": comment_user.id})
    response_data = perform_forum_request(
        "put",
        user_detail_url,
        data_or_params={"username": new_username},
    )
    if response_data["username"] != new_username:
        raise UpdateFailedException(url=user_detail_url, new_username=new_username)


def update_thread_username(thread_id, new_username):
    """
    Update username for discussion-forum threads via Forum APIs
    """
    thread_detail_url = Thread.url_with_id(params={"id": thread_id})
    response_data = perform_forum_request(
        "put",
        thread_detail_url,
        data_or_params={"username": new_username},
    )
    if response_data["username"] != new_username:
        raise UpdateFailedException(url=thread_detail_url, new_username=new_username)


def update_comment_username(comment_id, new_username):
    """
    Update username for discussion-forum comments via Forum APIs
    """
    comment_detail_url = Comment.url_for_comments(params={"parent_id": comment_id})
    response_data = perform_forum_request(
        "put",
        comment_detail_url,
        data_or_params={"username": new_username},
    )
    if response_data["username"] != new_username:
        raise UpdateFailedException(url=comment_detail_url, new_username=new_username)
