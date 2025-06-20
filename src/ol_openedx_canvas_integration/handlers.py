"""Event Handlers for the openedx-events signals."""

from django.dispatch import receiver
from openedx_events.content_authoring.signals import XBLOCK_DELETED, XBLOCK_PUBLISHED

from ol_openedx_canvas_integration.cms_tasks import sync_course_assignments_with_canvas


@receiver(XBLOCK_PUBLISHED)
def handle_xblock_publised_event(signal, sender, xblock_info, metadata, **kwargs):  # noqa: ARG001
    """
    Update Canvas assignments if the courses are linked.
    """
    sync_course_assignments_with_canvas.delay(str(xblock_info.usage_key.course_key))


@receiver(XBLOCK_DELETED)
def handle_xblock_deleted_event(signal, sender, xblock_info, metadata, **kwargs):  # noqa: ARG001
    """
    Update Canvas assignments if the courses are linked.
    """
    if xblock_info.block_type in ["chapter", "sequential"]:
        # Sometimes there is a race condition where the Canvas API calls are made
        # before the Course Outline has updated, leading to the assignments not getting
        # deleted in Canvas. So, a countdown of 10 seconds set to avoid it.
        sync_course_assignments_with_canvas.apply_async(
            args=[str(xblock_info.usage_key.course_key)],
            countdown=10,
        )
