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

    NOTE: This only works with the MySQL backend for Forum v2.
    The MongoDB backend is not supported and will create incorrect user records.
    Only use this plugin if your Open edX installation uses the MySQL-based
    forum backend.
    """
    try:
        # The forum API update_username method updates the user record
        # and replaces the username in all forum content (threads/comments)
        forum_api.update_username(
            user_id=str(user_id),
            new_username=new_username,
            course_id=None,  # None means update across all courses
        )
        log.info("Successfully updated forum username for user_id=%", user_id)
    except ForumV2RequestError as e:
        # Log but don't raise - user may not exist in forum yet
        log.warning("Could not update forum username for user_id=%: %", (user_id, e))
    except Exception:
        log.exception("Unexpected error updating forum username for user_id=%", user_id)
