"""
Utilities for the ol-openedx-course-sync plugin
"""

import logging
from uuid import uuid4

from cms.djangoapps.contentstore.utils import duplicate_block
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from edx_django_utils.cache import TieredCache, get_cache_key
from openedx.core.djangoapps.discussions.models import DiscussionsConfiguration
from openedx.core.djangoapps.django_comment_common.models import (
    CourseDiscussionSettings,
)
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.exceptions import ItemNotFoundError
from xmodule.tabs import CourseTabList, StaticTab

from ol_openedx_course_sync.constants import STATIC_TAB_TYPE
from ol_openedx_course_sync.models import CourseSyncMapping, CourseSyncOrganization

User = get_user_model()
log = logging.getLogger(__name__)


def copy_course_content(source_course_key, target_course_key, branch, user_id=None):
    """
    Copy course content from source_course to target_course
    on the specified branch.
    """
    module_store = modulestore()
    subtree_list = [module_store.make_course_usage_key(source_course_key)]
    source_course_key_for_branch = source_course_key.for_branch(branch)
    target_course_key_for_branch = target_course_key.for_branch(branch)

    source_modulestore = module_store._get_modulestore_for_courselike(source_course_key)  # noqa: SLF001
    target_modulestore = module_store._get_modulestore_for_courselike(target_course_key)  # noqa: SLF001
    if source_modulestore == target_modulestore:
        source_modulestore.copy(
            user_id,
            source_course_key_for_branch,
            target_course_key_for_branch,
            subtree_list,
        )


def copy_static_tabs(source_course_key, target_course_key, user):
    """
    Copy static tabs from source to target course.

    Args:
        source_course_key (CourseLocator): The course key of the source course.
        target_course_key (CourseLocator): The course key of the target course.
        user (User): The user performing the update.
    """
    store = modulestore()
    source_course = store.get_course(source_course_key)
    target_course = store.get_course(target_course_key)

    # If we need to update the static tabs, we will delete the
    # old static tabs and create new ones to handle the tab ordering.
    for tab in target_course.tabs:
        if tab.type != STATIC_TAB_TYPE:
            continue

        tab_usage_key = target_course.id.make_usage_key(STATIC_TAB_TYPE, tab.url_slug)
        existing_tabs = target_course.tabs or []

        # Remove the tab from the target course tabs list
        target_course.tabs = [
            tab
            for tab in existing_tabs
            if tab.get("url_slug") != tab_usage_key.block_id
        ]
        store.update_item(target_course, user.id)
        try:
            store.get_item(tab_usage_key, user.id)
        except ItemNotFoundError:
            # If the tab does not exist, we can skip deletion
            continue
        store.delete_item(tab_usage_key, user.id)

    # Now copy the static tabs from the source course to the target course
    # Steps:
    # 1. Iterate through the static tabs in the source course.
    # 2. For each static tab, create a new usage key for the target course.
    # 3. Duplicate the block from the source course to the target course.
    # 4. Update the target course's tabs list with the new tab
    target_course_usage_key = target_course.usage_key
    for source_tab in source_course.tabs:
        if source_tab.type != STATIC_TAB_TYPE:
            continue

        # Create a new usage key for the destination tab
        target_tab_usage_key = target_course_usage_key.replace(
            category=STATIC_TAB_TYPE, name=uuid4().hex
        )
        source_tab_usage_key = source_course.id.make_usage_key(
            STATIC_TAB_TYPE, source_tab.url_slug
        )

        duplicate_block(
            target_course_usage_key,
            source_tab_usage_key,
            user,
            dest_usage_key=target_tab_usage_key,
            display_name=source_tab.name,
            shallow=True,
        )

        source_tab_dict = source_tab.to_json()
        source_tab_dict["url_slug"] = target_tab_usage_key.block_id
        target_course.tabs.append(
            StaticTab(
                tab_dict=source_tab_dict,
                name=source_tab.name,
                url_slug=target_tab_usage_key.block_id,
            )
        )

    store.update_item(target_course, user.id)


def update_default_tabs(source_course_key, target_course_key, user):
    """
    Update the `is_hidden` tab state for the default tabs like wiki, and progress tab.

    Args:
        source_course_key (CourseLocator): The course key of the source course.
        target_course_key (CourseLocator): The course key of the target course.
        user (User): The user performing the update.
    """
    store = modulestore()
    source_course = store.get_course(source_course_key)
    target_course = store.get_course(target_course_key)
    is_updated = False

    for tab in source_course.tabs:
        if tab.type == STATIC_TAB_TYPE:
            continue

        target_course_tab = CourseTabList.get_tab_by_type(target_course.tabs, tab.type)
        if tab.is_hidden == target_course_tab.is_hidden:
            continue
        target_course_tab.is_hidden = tab.is_hidden
        is_updated = True

    if is_updated:
        store.update_item(target_course, user.id)


def sync_discussions_configuration(source_course_key, target_course_key, user):
    """
    Sync DiscussionsConfiguration and CourseDiscussionSettings
    from source to target course.

    Args:
        source_course_key (CourseKey): The key for the source course.
        target_course_key (CourseKey): The key for the target course.
    """

    def sync_model_objects(source_object, target_object):
        """
        Sync fields from source_object to target_object
        """
        fields = fields_to_sync[type(source_object)]
        has_changes = False
        for field in fields:
            if getattr(source_object, field) != getattr(target_object, field):
                has_changes = True
                setattr(target_object, field, getattr(source_object, field))

        if has_changes:
            target_object.save()

    fields_to_sync = {
        # `DiscussionsConfiguration` fields excluding context_key and history.
        DiscussionsConfiguration: [
            "enabled",
            "posting_restrictions",
            "lti_configuration",
            "enable_in_context",
            "enable_graded_units",
            "unit_level_visibility",
            "plugin_configuration",
            "provider_type",
        ],
        # `CourseDiscussionSettings` fields excluding course_id and discussions_id_map.
        CourseDiscussionSettings: [
            "always_divide_inline_discussions",
            "reported_content_email_notifications",
            "division_scheme",
            "_divided_discussions",
        ],
    }

    source_discussions_settings = CourseDiscussionSettings.get(source_course_key)
    target_discussions_settings = CourseDiscussionSettings.get(target_course_key)
    sync_model_objects(source_discussions_settings, target_discussions_settings)

    source_discussions_config = DiscussionsConfiguration.get(source_course_key)
    target_discussions_config = DiscussionsConfiguration.get(target_course_key)
    sync_model_objects(source_discussions_config, target_discussions_config)

    # update discussion settings in modulestore
    module_store = modulestore()
    source_course = module_store.get_course(source_course_key)
    target_course = module_store.get_course(target_course_key)

    target_course.discussions_settings = source_course.discussions_settings
    target_course.discussion_blackouts = source_course.discussion_blackouts
    target_course.discussion_topics = source_course.discussion_topics
    module_store.update_item(target_course, user.id)


def get_course_sync_service_user():
    """
    Retrieve the service user for course sync operations.

    Returns:
        User: The service user object.
    """
    cache_key = get_cache_key(
        course_sync_service_worker=settings.OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME
    )
    cache_value = TieredCache.get_cached_response(cache_key)
    if not cache_value.is_found:
        user = User.objects.filter(
            username=settings.OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME
        ).first()
        TieredCache.set_all_tiers(cache_key, user)
    else:
        user = cache_value.value

    return user


def get_syncable_course_mappings(course_key):
    """
    Check if course sync should be performed for the given course key.

    Returns:
        Queryset: QuerySet of CourseSyncMapping or None
    """
    # Check if organization is active for sync
    if not CourseSyncOrganization.objects.filter(
        organization=course_key.org, is_active=True
    ).exists():
        return None

    # Check if service worker username is configured
    if not getattr(settings, "OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME", None):
        error_msg = (
            "OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME is not set. "
            "Course sync will not be performed."
        )
        raise ImproperlyConfigured(error_msg)

    # Get active course sync mappings
    course_sync_mappings = CourseSyncMapping.objects.filter(
        source_course=course_key, is_active=True
    )
    if not course_sync_mappings:
        log.info("No mapping found for course %s. Skipping sync.", str(course_key))
        return None

    return course_sync_mappings
