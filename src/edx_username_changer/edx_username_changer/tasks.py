"""
This file contains celery tasks related to edx_username_changer plugin.
"""

import logging

from celery import shared_task
from django.contrib.auth import get_user_model
from forum import api as forum_api
from forum.utils import ForumV2RequestError

log = logging.getLogger(__name__)

User = get_user_model()


@shared_task()
def task_update_username_in_forum(user_id, new_username):
    """
    Update username in Discussion-Forum service using Forum v2 API.

    This works with both MongoDB and MySQL backends through Forum v2's
    backend abstraction layer.
    """
    try:
        # The forum API update_username method updates the user record
        # and replaces the username in all forum content (threads/comments)
        forum_api.update_username(
            user_id=str(user_id),
            new_username=new_username,
            course_id=None,  # None means update across all courses
        )
        log.info(f"Successfully updated forum username for user_id={user_id}")
    except ForumV2RequestError as e:
        # Log but don't raise - user may not exist in forum yet
        log.warning(f"Could not update forum username for user_id={user_id}: {e}")
    except Exception as e:  # noqa: BLE001
        log.error(
            f"Unexpected error updating forum username for user_id={user_id}: {e}"
        )
