from enum import StrEnum


class ContentType(StrEnum):
    """Enumeration for content types (Course or Library)."""

    COURSE = "course"
    LIBRARY = "library"

    @property
    def display_name(self):
        """Return the human-readable display name."""
        return self.value.capitalize()


# Library key prefixes for different versions
LIBRARY_V1_PREFIX = "library-v1:"
LIBRARY_V2_PREFIX = "lib:"

ENABLE_GIT_AUTO_EXPORT = "ENABLE_GIT_AUTO_EXPORT"
ENABLE_AUTO_GITHUB_REPO_CREATION = "ENABLE_AUTO_GITHUB_REPO_CREATION"
GITHUB_ORG = "GITHUB_ORG"
GITHUB_ACCESS_TOKEN = "GITHUB_ACCESS_TOKEN"  # noqa: S105

# Library-specific feature flags
ENABLE_GIT_AUTO_LIBRARY_EXPORT = "ENABLE_GIT_AUTO_LIBRARY_EXPORT"
ENABLE_AUTO_GITHUB_LIBRARY_REPO_CREATION = "ENABLE_AUTO_GITHUB_LIBRARY_REPO_CREATION"

COURSE_RERUN_STATE_SUCCEEDED = "succeeded"
REPOSITORY_NAME_MAX_LENGTH = 100  # Max length from GitHub for repo name

# Debounce settings for the signal handler. A course save or library import
# can fire many publish signals for the same content (up to one per block for
# a large v2 library import). Every signal still schedules a task, but this
# cache key holds a token overwritten by each one; a task only performs the
# real export if its token is still current when it wakes
# EXPORT_DEBOUNCE_DELAY seconds later. That dedupes the expensive git
# operations even though one Celery task is still enqueued per signal. A
# missing cache entry (e.g. evicted) exports anyway rather than silently
# dropping the export.
EXPORT_DEBOUNCE_DELAY = 5  # seconds of quiet before a scheduled export actually runs
EXPORT_DEBOUNCE_CACHE_KEY = "git_export_debounce:{content_key}"
