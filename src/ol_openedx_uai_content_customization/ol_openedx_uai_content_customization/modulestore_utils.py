"""
Modulestore wrappers for creating UAI course content.

All functions that write to the modulestore live here so that the management
command stays thin and these helpers can be mocked cleanly in tests.
"""

import logging
from contextlib import contextmanager

from cms.djangoapps.contentstore.utils import add_instructor, initialize_permissions
from django.contrib.auth import get_user_model
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.django import modulestore

log = logging.getLogger(__name__)


@contextmanager
def course_bulk_operations(course_key):
    """
    Context manager that batches modulestore writes for a single course.

    Wraps modulestore's bulk_operations to defer signal emissions and index
    updates, giving significantly better write performance when creating many
    child blocks at once.

    Args:
        course_key: The CourseKey for the course being written.
    """
    with modulestore().bulk_operations(course_key):
        yield


def create_course_in_modulestore(org, number, run, display_name, user_id):
    """
    Create a new course in the Split modulestore.

    Uses the ``default_store`` context manager (the correct API) rather than
    passing ``default_store`` as a kwarg, which is not supported.

    The ``create_course`` positional signature is:
        create_course(org, course, run, user_id, **kwargs)
    where the second argument is named ``course`` (not ``number``) in the
    MixedModuleStore API.  Passing it as a keyword argument with the wrong
    name (``number=``) is what caused the original TypeError.

    Raises:
        xmodule.modulestore.exceptions.DuplicateCourseError: if the course
        already exists.  Callers should catch this and handle accordingly.

    Args:
        org: Organisation string (e.g. "UAI_SOURCE").
        number: Course number string (e.g. "UAI.2.S.HC").
        run: Run string (e.g. "1T2026").
        display_name: Human-readable course title.
        user_id: ID of the user performing the operation.

    Returns:
        The newly-created course XBlock descriptor.
    """
    with modulestore().default_store(ModuleStoreEnum.Type.split):
        course = modulestore().create_course(
            org,
            number,
            run,
            user_id,
            fields={"display_name": display_name},
        )
    log.info("Created course: course-v1:%s+%s+%s (%s)", org, number, run, display_name)
    return course


def initialize_course_permissions(course_key, user_id):
    """
    Seed forum roles and enroll the creator so the course is fully operational.

    This mirrors what Studio does after every course creation:
    ``cms.djangoapps.contentstore.utils.initialize_permissions``.
    It must be called after the course has been created in the modulestore.

    Args:
        course_key: The CourseKey of the newly created course.
        user_id: ID of the user who created the course.
    """
    User = get_user_model()
    user = User.objects.get(id=user_id)
    # Mirror Studio's create_new_course_in_store: add instructor+staff roles first,
    # then seed forum roles and enroll the creator.
    add_instructor(course_key, user, user)
    initialize_permissions(course_key, user)
    log.info("Initialized permissions for course %s (user_id=%s)", course_key, user_id)


def create_section(course, display_name, user_id):
    """
    Add a chapter (section) to the course.

    Args:
        course: Course XBlock descriptor.
        display_name: Display name for the section.
        user_id: ID of the user performing the operation.

    Returns:
        The newly-created chapter XBlock descriptor.
    """
    store = modulestore()
    section = store.create_child(
        user_id,
        course.location,
        "chapter",
        fields={"display_name": display_name},
    )
    log.debug("Created section '%s' under %s", display_name, course.location)
    return section


def create_subsection(section, display_name, user_id):
    """
    Add a sequential (subsection) to the section.

    Args:
        section: Chapter XBlock descriptor.
        display_name: Display name for the subsection.
        user_id: ID of the user performing the operation.

    Returns:
        The newly-created sequential XBlock descriptor.
    """
    store = modulestore()
    subsection = store.create_child(
        user_id,
        section.location,
        "sequential",
        fields={"display_name": display_name},
    )
    log.debug("Created subsection '%s' under %s", display_name, section.location)
    return subsection


def create_unit(subsection, display_name, user_id):
    """
    Add a vertical (unit) to the subsection.

    Args:
        subsection: Sequential XBlock descriptor.
        display_name: Display name for the unit.
        user_id: ID of the user performing the operation.

    Returns:
        The newly-created vertical XBlock descriptor.
    """
    store = modulestore()
    unit = store.create_child(
        user_id,
        subsection.location,
        "vertical",
        fields={"display_name": display_name},
    )
    log.debug("Created unit '%s' under %s", display_name, subsection.location)
    return unit


def create_video_block(unit, display_name, edx_video_id, user_id):
    """
    Add a video XBlock to the unit.

    Args:
        unit: Vertical XBlock descriptor.
        display_name: Display name for the video block.
        edx_video_id: The Open edX video UUID string (from the video asset CSV).
        user_id: ID of the user performing the operation.

    Returns:
        The newly-created video XBlock descriptor.
    """
    store = modulestore()
    video = store.create_child(
        user_id,
        unit.location,
        "video",
        fields={
            "display_name": display_name,
            "edx_video_id": edx_video_id,
        },
    )
    log.debug(
        "Created video block '%s' (edx_video_id=%s) under %s",
        display_name,
        edx_video_id,
        unit.location,
    )
    return video


def publish_course(course, user_id):
    """
    Publish the entire course tree so it becomes visible in the LMS.

    Publishes each top-level section (chapter) individually.  The Split
    modulestore's publish is recursive, so publishing a section also publishes
    all its sequentials, verticals, and video blocks.  Publishing at the
    section level (rather than the course root) ensures that newly-created
    child blocks — which live in the draft branch — are included.

    Args:
        course: Course XBlock descriptor identifying the course to publish.
        user_id: ID of the user performing the operation.
    """
    store = modulestore()
    sections = store.get_items(
        course.id,
        qualifiers={"category": "chapter"},
    )
    for section in sections:
        store.publish(section.location, user_id)
        log.debug("Published section %s", section.location)
    log.info("Published %d section(s) for course %s", len(sections), course.id)
