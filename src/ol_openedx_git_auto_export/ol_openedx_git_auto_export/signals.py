"""
Signal handlers for the git auto-export plugin.

This module contains Django signal handlers that respond to course/library publishing,
creation, and rerun events to automatically create GitHub repositories and
export content to them.
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
    export_library_to_git,
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
        async_create_github_repo.delay(str(instance.course_key), export_content=True)


# Library Signal Receivers
def listen_for_library_v1_updated(sender, library_key, **kwargs):  # noqa: ARG001
    """
    Receives library update signal and performs export workflow.

    This is triggered when a library is updated/published in Studio.

    Args:
        sender: The signal sender
        library_key: LibraryLocator - The key of the library that was updated
        **kwargs: Additional signal parameters
    """
    log.info("Library v1 updated signal received for library: %s", library_key)
    export_library_to_git(library_key)


def listen_for_library_v2_created(**kwargs):
    """
    Handle library v2 created signal to create a GitHub repository for the library.

    NOTE: This is ONLY for Library v2 (lib:org:slug format).
    Library v1 (library-v1:org+library format) does NOT have a creation signal.

    This is triggered when a new library v2 is created in Studio via the
    CONTENT_LIBRARY_CREATED signal from openedx_events.

    Args:
        **kwargs: Signal parameters including 'content_library' with ContentLibraryData
    """
    content_library = kwargs.get("content_library")
    if content_library:
        library_key = content_library.library_key
        log.info("Library v2 created signal received for library: %s", library_key)

        if is_auto_repo_creation_enabled(is_library=True):
            async_create_github_repo.delay(str(library_key), export_content=True)


def listen_for_library_v2_updated(**kwargs):
    """
    Handle library v2 metadata updated signal to export content to GitHub repository.

    This is triggered when a library v2 metadata (title, description, etc.) is updated
    in Studio via the CONTENT_LIBRARY_UPDATED signal from openedx_events.

    Note: This does NOT fire when blocks/components are added or modified.

    Args:
        **kwargs: Signal parameters including 'content_library' with ContentLibraryData
    """
    content_library = kwargs.get("content_library")
    if content_library:
        library_key = content_library.library_key
        log.info(
            "Library v2 metadata updated signal received for library: %s", library_key
        )

        export_library_to_git(library_key)


def listen_for_library_block_published(**kwargs):
    """
    Handle library block published signal to export content to GitHub repository.

    This is triggered when a new block/component is added to a v2 library
    via the LIBRARY_BLOCK_PUBLISHED signal from openedx_events.

    Args:
        **kwargs: Signal parameters including 'library_block' with LibraryBlockData
    """
    library_block = kwargs.get("library_block")
    if library_block:
        # Extract library key from the usage key
        usage_key = library_block.usage_key
        library_key = usage_key.context_key
        log.info(
            "Library v2 block published signal received for block %s in library: %s",
            usage_key,
            library_key,
        )

        export_library_to_git(library_key)


def listen_for_library_container_published(**kwargs):
    """
    Handle library container published signal to export content to GitHub repository.

    This is triggered when a new container is added to a v2 library
    via the LIBRARY_CONTAINER_PUBLISHED signal from openedx_events.

    Args:
        **kwargs: Signal parameters including 'library_container' with
          LibraryContainerData
    """
    library_container = kwargs.get("library_container")
    if library_container:
        # Extract library key from the container key
        container_key = library_container.container_key
        library_key = container_key.lib_key
        log.info(
            "Library v2 container published signal received for "
            "container %s in library: %s",
            container_key,
            library_key,
        )

        export_library_to_git(library_key)
