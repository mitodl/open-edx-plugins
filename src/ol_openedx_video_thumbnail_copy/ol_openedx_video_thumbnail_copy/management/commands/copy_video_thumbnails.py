"""Copy a course's missing video thumbnails from another edxapp's public media URL."""

from urllib.parse import quote

import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from edxval.models import VideoImage
from edxval.utils import get_video_image_storage

REQUEST_TIMEOUT_SECONDS = 30


class Command(BaseCommand):
    """Copy a course's missing video thumbnails under their existing keys."""

    help = __doc__

    def add_arguments(self, parser):
        """Add the course key and the source media URL."""
        parser.add_argument("course_key", help="Course key on this instance.")
        parser.add_argument(
            "source_base_url",
            help="e.g. https://xpro-production-edxapp-storage.s3.amazonaws.com/media/",
        )

    def handle(self, course_key, source_base_url, **options):  # noqa: ARG002
        """Copy each thumbnail key that is missing from local storage."""
        storage = get_video_image_storage()
        names = VideoImage.objects.filter(
            course_video__course_id=course_key
        ).values_list("image", flat=True)
        keys = sorted({name for name in names if name})
        if not keys:
            self.stderr.write(f"No video thumbnails found for {course_key}")
        for key in keys:
            try:
                self.copy_thumbnail(storage, key, source_base_url)
            except Exception as exc:  # noqa: BLE001
                # Keep going: a key that always fails (e.g. one storage rejects)
                # would otherwise block every key after it on each re-run.
                self.stderr.write(f"missing {key}: {exc!r}")

    def copy_thumbnail(self, storage, key, source_base_url):
        """Download one thumbnail and save it under the same key, unless present."""
        if storage.exists(key):
            self.stdout.write(f"skipped {key}")
            return
        url = f"{source_base_url.rstrip('/')}/{quote(key)}"
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        content_type = response.headers.get("Content-Type", "")
        # A non-image 200 usually means a wrong base URL; saving it would stick.
        if response.ok and content_type.startswith("image/"):
            storage.save(key, ContentFile(response.content))
            self.stdout.write(f"copied {key}")
        else:
            self.stderr.write(
                f"missing {key}: HTTP {response.status_code} {content_type}"
            )
