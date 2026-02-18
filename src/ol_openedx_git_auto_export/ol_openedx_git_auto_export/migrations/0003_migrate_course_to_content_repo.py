# Generated migration to migrate data from CourseGitRepository to ContentGitRepository

from django.db import migrations
from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.locator import LibraryLocator


def migrate_course_to_content_repos(apps, schema_editor):  # noqa: ARG001
    """
    Migrate all CourseGitRepository entries to ContentGitRepository.

    This function:
    1. Copies all data from CourseGitRepository to ContentGitRepository
    2. Preserves all fields including created/modified timestamps
    3. Skips entries that already exist in ContentGitRepository
    """
    CourseGitRepository = apps.get_model(
        "ol_openedx_git_auto_export", "CourseGitRepository"
    )
    ContentGitRepository = apps.get_model(
        "ol_openedx_git_auto_export", "ContentGitRepository"
    )

    migrated_count = 0
    skipped_count = 0

    for course_repo in CourseGitRepository.objects.all():
        # Check if already migrated
        if not ContentGitRepository.objects.filter(
            content_key=course_repo.course_key
        ).exists():
            ContentGitRepository.objects.create(
                content_key=course_repo.course_key,
                git_url=course_repo.git_url,
                is_export_enabled=course_repo.is_export_enabled,
                created=course_repo.created,
                modified=course_repo.modified,
            )
            migrated_count += 1
        else:
            skipped_count += 1


def reverse_migration(apps, schema_editor):  # noqa: ARG001
    """
    Reverse migration: Copy ContentGitRepository entries back to CourseGitRepository.

    Only migrates entries that have CourseKey (not LibraryLocator).
    """

    CourseGitRepository = apps.get_model(
        "ol_openedx_git_auto_export", "CourseGitRepository"
    )
    ContentGitRepository = apps.get_model(
        "ol_openedx_git_auto_export", "ContentGitRepository"
    )

    migrated_count = 0
    skipped_count = 0

    for content_repo in ContentGitRepository.objects.all():
        # Parse the content_key to check if it's a course
        try:
            content_key = CourseKey.from_string(str(content_repo.content_key))
            is_library = isinstance(content_key, LibraryLocator)

            # Only migrate courses, not libraries
            if not is_library:
                if not CourseGitRepository.objects.filter(
                    course_key=content_repo.content_key
                ).exists():
                    CourseGitRepository.objects.create(
                        course_key=content_repo.content_key,
                        git_url=content_repo.git_url,
                        is_export_enabled=content_repo.is_export_enabled,
                        created=content_repo.created,
                        modified=content_repo.modified,
                    )
                    migrated_count += 1
                else:
                    skipped_count += 1
        except Exception:  # noqa: BLE001
            # Skip entries that can't be parsed
            skipped_count += 1


class Migration(migrations.Migration):
    dependencies = [
        ("ol_openedx_git_auto_export", "0002_contentgitrepository"),
    ]

    operations = [
        migrations.RunPython(migrate_course_to_content_repos, reverse_migration),
    ]
