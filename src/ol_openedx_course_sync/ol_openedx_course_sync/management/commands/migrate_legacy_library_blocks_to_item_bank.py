"""
Management command to migrate legacy (v1) library_content blocks in course(s)
to reference v2 library item bank blocks.

This command can be run for all the source courses or for a given list of courses.
"""

from __future__ import annotations

import logging

from cms.djangoapps.contentstore.tasks import (
    migrate_course_legacy_library_blocks_to_item_bank,
)
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from ol_openedx_course_sync.utils import (
    get_all_source_courses,
    get_course_sync_service_user,
)

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Migrate legacy library_content blocks in course(s) to reference v2 library
    item bank blocks.

    Examples:
        # Migrate legacy library content blocks for two courses.
        $ ./manage.py cms migrate_legacy_library_blocks_to_item_bank
        --course-id course-v1:edX+DemoX.1+2014 --course-id course-v1:edX+DemoX.2+2015

        # Migrate legacy library content blocks for all source courses.
        $ ./manage.py cms migrate_legacy_library_blocks_to_item_bank --all-courses

        # Also re-publish blocks that were already published before the migration.
        $ ./manage.py cms migrate_legacy_library_blocks_to_item_bank --all-courses \
        --publish-if-was-published
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--all-source-courses",
            action="store_true",
            help=_("Migrate legacy library content blocks for all source courses."),
        )
        parser.add_argument(
            "--course-id",
            metavar=_("COURSE_KEY"),
            action="append",
            dest="course_ids",
            default=[],
            help=_(
                "Migrate legacy library content blocks for the "
                "given course key. Can be repeated."
            ),
        )
        parser.add_argument(
            "--publish-if-was-published",
            action="store_true",
            help=_(
                "Re-publish migrated blocks that were already "
                "published prior to the migration."
            ),
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """
        Handle command
        """
        all_source_courses = options["all_source_courses"]
        course_ids = options["course_ids"]
        publish_if_was_published = options["publish_if_was_published"]

        if not course_ids and not all_source_courses:
            error_msg = (
                "Either --course-id or --all-courses argument should be provided."
            )
            raise CommandError(error_msg)
        if all_source_courses and course_ids:
            error_msg = (
                "Only one of --course-id or --all-courses argument should be provided."
            )
            raise CommandError(error_msg)

        # Check if service worker username is configured
        if not getattr(
            settings, "OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME", None
        ):
            error_msg = (
                "OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME is not set. "
                "Course sync will not be performed."
            )
            raise CommandError(error_msg)

        user = get_course_sync_service_user()
        course_keys = get_all_source_courses() if all_source_courses else course_ids
        for course_key in course_keys:
            try:
                CourseKey.from_string(str(course_key))
            except InvalidKeyError:
                error_msg = f"Invalid course key: {course_key}, skipping.."
                log.error(error_msg)  # noqa: TRY400
                continue
            msg = (
                f"Queuing legacy library content block "
                f"migration for course: {course_key}"
            )
            log.info(msg)
            migrate_course_legacy_library_blocks_to_item_bank.delay(
                user.id,
                str(course_key),
                publish_if_was_published,
            )
