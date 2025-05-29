"""
Utilities for the ol-openedx-course-sync plugin
"""

from xmodule.modulestore.django import modulestore


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
