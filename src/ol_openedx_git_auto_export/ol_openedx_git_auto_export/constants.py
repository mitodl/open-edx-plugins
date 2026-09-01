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

# Debounce settings for the signal handler.
# A single course save triggers 10-30 COURSE_PUBLISHED signals in one request,
# and importing a course into a v2 library fires one LIBRARY_BLOCK_PUBLISHED/
# LIBRARY_CONTAINER_PUBLISHED signal per block/container imported — a burst that
# can run far longer than any fixed window for a large import.
# This is a trailing-edge debounce: the cache key holds the id of the most
# recently scheduled task. Each new signal revokes that pending task and
# reschedules a fresh one, so the export only actually runs once
# EXPORT_DEBOUNCE_DELAY seconds pass with no new signal.
EXPORT_DEBOUNCE_DELAY = 5  # seconds of quiet required before the export actually runs
EXPORT_DEBOUNCE_CACHE_KEY = "git_export_debounce:{content_key}"
