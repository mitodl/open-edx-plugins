"""
Queue git exports for courses and libraries without waiting for a publish event.

Use it to re-push content whose export failed. Fix the cause of the failure
first, or the re-queued exports will fail the same way.

Usage:
    python manage.py cms export_to_git --content-keys <key> [<key> ...]
    python manage.py cms export_to_git --all [--dry-run]
"""

from django.core.management.base import BaseCommand, CommandError
from ol_openedx_git_auto_export.models import ContentGitRepository
from ol_openedx_git_auto_export.utils import queue_git_exports


class Command(BaseCommand):
    """Queue git exports for courses and libraries on demand."""

    help = "Queue git exports for courses and libraries on demand"

    def add_arguments(self, parser):
        target = parser.add_mutually_exclusive_group(required=True)
        target.add_argument(
            "--content-keys",
            nargs="+",
            metavar="KEY",
            help="Space-separated course or library keys to export",
        )
        target.add_argument(
            "--all",
            action="store_true",
            help="Export every repository with export enabled",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List what would be queued without queueing anything",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        if options["all"]:
            enabled = ContentGitRepository.objects.filter(is_export_enabled=True)
            key_strings = map(str, enabled.values_list("content_key", flat=True))
        else:
            key_strings = options["content_keys"]
        queued, skipped, errored = queue_git_exports(
            key_strings, dry_run=options["dry_run"]
        )

        verb = "Would queue" if options["dry_run"] else "Queued"
        self.stdout.write(self.style.SUCCESS(f"{verb} {len(queued)} export(s):"))
        for key in queued:
            self.stdout.write(f"  • {key}")
        self._report(f"Skipped {len(skipped)}:", skipped, self.style.WARNING)
        self._report(f"Errored {len(errored)}:", errored, self.style.ERROR)
        # Named keys are the operator's intent, so skipping one is a failure;
        # under --all, rows left behind by deleted content are expected.
        if errored or (options["content_keys"] and skipped):
            msg = f"{len(errored)} key(s) errored, {len(skipped)} skipped"
            raise CommandError(msg)

    def _report(self, title, entries, style):
        if not entries:
            return
        self.stdout.write(style(title))
        for key, reason in entries:
            self.stdout.write(style(f"  • {key}: {reason}"))
