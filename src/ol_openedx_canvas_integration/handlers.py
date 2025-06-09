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
        sync_course_assignments_with_canvas.delay(str(xblock_info.usage_key.course_key))
