"""
Utilities for the ol-openedx-course-sync plugin
"""

from uuid import uuid4

from cms.djangoapps.contentstore.utils import duplicate_block
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.exceptions import ItemNotFoundError
from xmodule.tabs import CourseTabList, StaticTab

from ol_openedx_course_sync.constants import STATIC_TAB_TYPE


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
