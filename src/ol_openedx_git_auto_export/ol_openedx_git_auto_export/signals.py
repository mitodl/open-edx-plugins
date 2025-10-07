"""
Signal handlers for the git auto-export plugin.

This module contains Django signal handlers that respond to course publishing,
creation, and rerun events to automatically create GitHub repositories and
export course content to them.
"""

import logging

from common.djangoapps.course_action_state.models import CourseRerunState
from django.db.models.signals import post_save
from django.dispatch import receiver

from ol_openedx_git_auto_export.constants import (
    COURSE_RERUN_STATE_SUCCEEDED,
)
from ol_openedx_git_auto_export.tasks import (
    async_create_github_repo,
)
from ol_openedx_git_auto_export.utils import (
    export_course_to_git,
    is_auto_repo_creation_enabled,
)

log = logging.getLogger(__name__)


def listen_for_course_publish(
    sender,  # noqa: ARG001
    course_key,
    **kwargs,  # noqa: ARG001
):  # pylint: disable=unused-argument
    """
    Receives publishing signal and performs publishing related workflows
    """
    export_course_to_git(course_key)


def listen_for_course_created(**kwargs):
    """
    Handle course created signal to create a GitHub repository for the course
    """
    course_key = kwargs.get("course").course_key

    if is_auto_repo_creation_enabled():
        async_create_github_repo.delay(str(course_key))


@receiver(post_save, sender=CourseRerunState)
def listen_for_course_rerun_state_post_save(sender, instance, **kwargs):  # noqa: ARG001
    """
    Listen for `CourseRerunState` post_save and
    create GitHub repository and export course content for successfully rerun courses
    """
    if instance.state != COURSE_RERUN_STATE_SUCCEEDED:
        return

    if is_auto_repo_creation_enabled():
        async_create_github_repo.delay(str(instance.course_key), export_course=True)
