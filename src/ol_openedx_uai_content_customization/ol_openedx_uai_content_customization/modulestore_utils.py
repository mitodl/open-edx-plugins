"""
Modulestore wrappers for creating UAI course content.

All functions that write to the modulestore live here so that the management
command stays thin and these helpers can be mocked cleanly in tests.
"""

import logging

from cms.djangoapps.contentstore.xblock_storage_handlers.view_handlers import (
    save_xblock_with_callback,
)
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.inheritance import own_metadata

from ol_openedx_uai_content_customization.constants import (
    BLOCK_TYPE_CHAPTER,
    BLOCK_TYPE_VIDEO,
)

log = logging.getLogger(__name__)


def clone_course_in_modulestore(  # noqa: PLR0913
    source_course_key, dest_org, dest_number, dest_run, display_name, user_id
):
    """
    Clone an existing course into a new course key in the Split modulestore.

    Uses ``modulestore().default_store`` as a context manager to ensure the
    destination course lands in the Split store — mirroring how Studio's own
    course-rerun feature works.  The ``display_name`` field is overridden in
    the clone so each UAI variant carries its own title.

    Raises:
        xmodule.modulestore.exceptions.DuplicateCourseError: if the destination
        course already exists.  Callers should catch this and handle accordingly.

    Args:
        source_course_key: CourseKey of the base course to clone.
        dest_org: Organisation string for the new course.
        dest_number: Course-number string for the new course (e.g. "UAI.2.S.HC").
        dest_run: Run string for the new course (e.g. "1T2026").
        display_name: Human-readable title for the cloned course.
        user_id: ID of the user performing the operation.

    Returns:
        The cloned course XBlock descriptor.
    """
    store = modulestore()
    with store.default_store(ModuleStoreEnum.Type.split):
        dest_course_key = store.make_course_key(dest_org, dest_number, dest_run)
        course = store.clone_course(
            source_course_key,
            dest_course_key,
            user_id,
            fields={"display_name": display_name},
        )
    log.info(
        "Cloned course %s -> course-v1:%s+%s+%s (%s)",
        source_course_key,
        dest_org,
        dest_number,
        dest_run,
        display_name,
    )
    return course


def delete_course_sections(course, user_id):
    """
    Delete all top-level sections (chapters) from the course.

    Called immediately after cloning the base course so the new course starts
    empty before UAI-specific content is added.  In the Split modulestore the
    course structure is versioned: old sections become part of the version
    history and are not surfaced once the new sections are published.

    Args:
        course: Course XBlock descriptor.
        user_id: ID of the user performing the operation.

    Returns:
        Number of sections deleted.
    """
    store = modulestore()
    sections = store.get_items(
        course.id,
        qualifiers={"category": BLOCK_TYPE_CHAPTER},
    )
    for section in sections:
        store.delete_item(section.location, user_id)
        log.debug("Deleted cloned section %s", section.location)
    count = len(sections)
    log.info("Deleted %d cloned section(s) from course %s", count, course.id)
    return count


def create_content_block(parent, block_type, display_name, user_id, **extra_fields):
    """
    Add a content block under the given parent XBlock.

    Args:
        parent: Parent XBlock descriptor that will own the new child.
        block_type: XBlock category to create (e.g. chapter, sequential,
            vertical, video).
        display_name: Display name for the created block.
        user_id: ID of the user performing the operation.
        **extra_fields: Optional additional fields for block creation.

    Returns:
        The newly-created child XBlock descriptor.
    """
    store = modulestore()
    fields = {"display_name": display_name, **extra_fields}
    block = store.create_child(
        user_id,
        parent.location,
        block_type,
        fields=fields,
    )

    if block_type == BLOCK_TYPE_VIDEO and "edx_video_id" in extra_fields:
        log.debug(
            "Created %s block '%s' (edx_video_id=%s) under %s",
            block_type,
            display_name,
            extra_fields["edx_video_id"],
            parent.location,
        )
    else:
        log.debug(
            "Created %s block '%s' under %s",
            block_type,
            display_name,
            parent.location,
        )

    return block


def save_video_block_with_edx_video_id(video_block, user, edx_video_id):
    """
    Save a newly-created video block using the CMS callback pipeline.

    This mirrors Studio's save flow and normalizes legacy fallback fields so
    an explicit ``edx_video_id`` is used as the canonical playback source.

    Args:
        video_block: Video XBlock descriptor created in modulestore.
        user: Django user object performing the operation.
        edx_video_id: VAL/Open edX video identifier to bind to the block.

    Returns:
        Updated video block descriptor returned by save callback utility.
    """
    old_metadata = own_metadata(video_block)
    video_block.edx_video_id = edx_video_id.strip()

    # Keep legacy fallback metadata empty to avoid default placeholder IDs.
    for field_name, value in (
        ("youtube_id_0_75", ""),
        ("youtube_id_1_0", ""),
        ("youtube_id_1_25", ""),
        ("youtube_id_1_5", ""),
        ("sub", ""),
        ("source", ""),
        ("html5_sources", []),
    ):
        if hasattr(video_block, field_name):
            setattr(video_block, field_name, value)

    return save_xblock_with_callback(
        video_block,
        user,
        old_metadata=old_metadata,
    )
