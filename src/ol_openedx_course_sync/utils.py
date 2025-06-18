"""
Utilities for the ol-openedx-course-sync plugin
"""

from uuid import uuid4

from cms.djangoapps.contentstore.utils import duplicate_block
from django.contrib.auth.models import User
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.exceptions import ItemNotFoundError
from xmodule.tabs import CourseTabList, StaticTab


def copy_course_content(source_course_key, target_course_key, branch):
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
        user_id = None
        source_modulestore.copy(
            user_id,
            source_course_key_for_branch,
            target_course_key_for_branch,
            subtree_list,
        )


def course_tabs_need_update(source_course, target_course):
    """
    Check if the source and target course have same static tabs.
    """
    if len(source_course.tabs) != len(target_course.tabs):
        return True

    for source_tab_idx, source_tab in enumerate(source_course.tabs):
        # We only do comparison of static tabs here
        if source_tab.type != "static_tab":
            continue

        # get the target tab at the same index to fix the ordering
        target_tab = target_course.tabs[source_tab_idx]
        if target_tab.type != "static_tab" or (
            target_tab.name != source_tab.name
            and target_tab.is_hidden != source_tab.is_hidden
        ):
            return True

        source_tab_usage_key = source_course.id.make_usage_key(
            "static_tab", source_tab.url_slug
        )
        target_tab_usage_key = target_course.id.make_usage_key(
            "static_tab", target_tab.url_slug
        )

        store = modulestore()
        try:
            source_tab_block = store.get_item(source_tab_usage_key)
            target_tab_block = store.get_item(target_tab_usage_key)
        except ItemNotFoundError:
            return True

        if source_tab_block.data != target_tab_block.data:
            return True
    return False


def copy_static_tabs(source_course_key, target_course_key):
    """
    Copy static tabs from source to target course.
    """
    store = modulestore()
    source_course = store.get_course(source_course_key)
    target_course = store.get_course(target_course_key)

    if not course_tabs_need_update(source_course, target_course):
        return

    # If we need to update the static tabs, we will delete the
    # old static tabs and create new ones to handle the tab ordering.
    for tab in target_course.tabs:
        if tab.type != "static_tab":
            continue

        tab_usage_key = target_course.id.make_usage_key("static_tab", tab.url_slug)
        existing_tabs = target_course.tabs or []
        target_course.tabs = [
            tab
            for tab in existing_tabs
            if tab.get("url_slug") != tab_usage_key.block_id
        ]
        store.update_item(target_course, User.objects.last().id)
        store.delete_item(tab_usage_key, User.objects.last().id)

    target_course_usage_key = target_course.usage_key
    for source_tab in source_course.tabs:
        if source_tab.type != "static_tab":
            continue

        # Create a new usage key for the destination tab
        target_tab_usage_key = target_course_usage_key.replace(
            category="static_tab", name=uuid4().hex
        )
        source_tab_usage_key = source_course.id.make_usage_key(
            "static_tab", source_tab.url_slug
        )

        duplicate_block(
            target_course_usage_key,
            source_tab_usage_key,
            User.objects.last(),
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
        store.update_item(target_course, User.objects.last().id)


def update_default_tabs(source_course_key, target_course_key):
    """
    Update the `is_hidden` tab state for the default tabs like wiki, and progress tab.
    """
    store = modulestore()
    source_course = store.get_course(source_course_key)
    target_course = store.get_course(target_course_key)
    is_updated = False

    for tab in source_course.tabs:
        target_course_tab = CourseTabList.get_tab_by_type(target_course.tabs, tab.type)
        if tab.is_hidden == target_course_tab.is_hidden:
            continue
        target_course_tab.is_hidden = tab.is_hidden
        is_updated = True

    if is_updated:
        store.update_item(target_course, User.objects.last().id)
