"""
This file contains celery tasks related to edx_username_changer plugin.
"""

from celery import shared_task
from django.contrib.auth import get_user_model
from openedx.core.djangoapps.django_comment_common.comment_client.user import (
    User as CommentUser,
)

from edx_username_changer.utils import (
    get_authored_threads_and_comments,
    get_enrolled_course_ids,
    update_comment_user_username,
    update_comment_username,
    update_thread_username,
)

COMMENT_TYPE = "comment"
THREAD_TYPE = "thread"
User = get_user_model()


@shared_task()
def task_update_username_in_forum(username):
    """
    Change username in Discussion-Forum service
    """
    user = User.objects.get(username=username)
    comment_user = CommentUser.from_django_user(user)
    update_comment_user_username(comment_user, user.username)
    enrolled_course_ids = get_enrolled_course_ids(user)
    authored_items = get_authored_threads_and_comments(
        comment_user, enrolled_course_ids
    )

    for authored_item in authored_items:
        item_id = authored_item["id"]
        item_type = str(authored_item.get("type"))
        if item_type == THREAD_TYPE:
            update_thread_username(item_id, user.username)
        elif item_type == COMMENT_TYPE:
            update_comment_username(item_id, user.username)
