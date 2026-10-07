"""Backfill existing course access roles to the enrollment webhook consumer."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

# Rows are walked a page at a time rather than through .iterator(). Both keep
# memory bounded, but .iterator() holds a server-side cursor open across the
# dispatch below, and a deployment running tasks eagerly closes the database
# connection when a task finishes -- which breaks that cursor mid-backfill with
# "MySQL server has gone away". Paging by primary key keeps no cursor open.
BATCH_SIZE = 500


class Command(BaseCommand):
    """
    Send the enrollment webhook for course access roles that already exist.

    Org-wide roles (a CourseAccessRole with no course_id) are skipped: the
    consumer keys its records on a single course run, so there is nothing to
    send them against.
    """

    help = "Send the enrollment webhook for existing course access roles."

    def add_arguments(self, parser):
        parser.add_argument(
            "--course-id",
            action="append",
            dest="course_ids",
            help=(
                "Limit to this course ID. Repeat for several; omit for every course."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List what would be sent without queueing anything.",
        )

    def handle(self, *_args, **options):
        from common.djangoapps.student.models import (  # noqa: PLC0415
            CourseAccessRole,
        )

        from ol_openedx_events_handler.tasks import (  # noqa: PLC0415
            notify_course_access_role_addition,
        )
        from ol_openedx_events_handler.utils import (  # noqa: PLC0415
            validate_enrollment_webhook,
        )

        # Raise rather than return: a backfill that no-ops on a misconfigured
        # install would still exit 0, leaving an automated run unable to tell
        # "nothing to send" from "never tried".
        if not validate_enrollment_webhook():
            msg = (
                "The enrollment webhook is not configured. Set "
                "ENROLLMENT_WEBHOOK_URL and ENROLLMENT_WEBHOOK_ACCESS_TOKEN."
            )
            raise CommandError(msg)

        allowed_roles = getattr(settings, "ENROLLMENT_COURSE_ACCESS_ROLES", [])
        if not allowed_roles:
            msg = "ENROLLMENT_COURSE_ACCESS_ROLES is empty, so no role would be sent."
            raise CommandError(msg)

        roles = CourseAccessRole.objects.filter(role__in=allowed_roles).select_related(
            "user"
        )
        if options["course_ids"]:
            roles = roles.filter(course_id__in=options["course_ids"])

        dry_run = options["dry_run"]
        sent = skipped_org_wide = skipped_no_email = 0

        last_id = 0
        while True:
            batch = list(roles.filter(id__gt=last_id).order_by("id")[:BATCH_SIZE])
            if not batch:
                break
            last_id = batch[-1].id

            for access_role in batch:
                # A blank course_id reads back as None, so an org-wide role has
                # no run to send against.
                course_key = str(access_role.course_id or "")
                if not course_key:
                    skipped_org_wide += 1
                    continue

                email = access_role.user.email
                if not email:
                    self.stderr.write(
                        self.style.WARNING(
                            f"Skipping user {access_role.user.username}: no email."
                        )
                    )
                    skipped_no_email += 1
                    continue

                self.stdout.write(f"{email} — {access_role.role} in {course_key}")
                if not dry_run:
                    notify_course_access_role_addition.delay(
                        user_email=email,
                        course_key=course_key,
                        role=access_role.role,
                    )
                sent += 1

        verb = "Would send" if dry_run else "Queued"
        # Broken out by reason: an org-wide skip is expected, a missing email is
        # a data problem worth chasing, and one total cannot tell them apart.
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {sent} role(s); skipped {skipped_org_wide} org-wide "
                f"and {skipped_no_email} with no email."
            )
        )
