"""
Utility methods for ol-openedx-course-propagator plugin
"""
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.django import SignalHandler
from xmodule.modulestore import ModuleStoreEnum
from opaque_keys.edx.locator import CourseLocator
from xmodule.modulestore.django import SignalHandler

from ol_openedx_course_propagator.models import CourseSyncMasterOrg, CourseSyncMapping
from ol_openedx_course_propagator.tasks import async_course_propagator

log = logging.getLogger(__name__)


@receiver(SignalHandler.course_published)
def listen_for_course_publish(
    sender,  # noqa: ARG001
    course_key,
    **kwargs,  # noqa: ARG001
):
    """
    Copy course content from source course to destination course.
    """
    if CourseSyncMasterOrg.objects.filter(organization=course_key.org).exists():
        # Get the source and destination course IDs
        course_sync_mapping = CourseSyncMapping.objects.filter(
            source_course=course_key
        ).first()
        if course_sync_mapping:
            source_course = str(course_sync_mapping.source_course)
            user_id = 2
            for target_course_key in course_sync_mapping.target_courses.split(","):
                # Call the async task to copy the course content
                async_course_propagator.delay(user_id, source_course, target_course)
        else:
            log.warning(
                "No mapping found for course %s. Skipping copy.", course_key.id
            )
            return

