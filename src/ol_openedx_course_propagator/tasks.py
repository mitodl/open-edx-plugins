from celery import shared_task  # pylint: disable=import-error
from celery.utils.log import get_task_logger
from cms.djangoapps.contentstore.git_export_utils import GitExportError, export_to_git
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.django import modulestore

LOGGER = get_task_logger(__name__)


@shared_task
def async_course_propagator(user_id, source_course_id, dest_course_id):
    module_store = modulestore()
    source_course_key = CourseLocator.from_string(source_course_id)
    source_course_draft = source_course_key.for_branch("draft-branch")
    source_course_published = source_course_key.for_branch("published-branch")
    subtree_list = [module_store.make_course_usage_key(source_course_key)]

    dest_course_key = CourseLocator.from_string(dest_course_id)
    dest_course_draft = dest_course_key.for_branch("draft-branch")
    dest_course_published = dest_course_key.for_branch("published-branch")

    source_modulestore = module_store._get_modulestore_for_courselike(source_course_key)
    # for a temporary period of time, we may want to hardcode dest_modulestore as split if there's a split
    # to have only course re-runs go to split. This code, however, uses the config'd priority
    dest_modulestore = module_store._get_modulestore_for_courselike(dest_course_key)
    if source_modulestore == dest_modulestore:
        source_modulestore.copy(user_id, source_course_draft, dest_course_draft, subtree_list)
        source_modulestore.copy(user_id, source_course_published, dest_course_published, subtree_list)
        SignalHandler.course_published.send(sender=None, course_key=dest_course_key)
        return
