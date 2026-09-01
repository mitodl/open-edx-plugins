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
# a large v2 library import). Two cache keys collapse that burst into a single
# export without queuing a task per signal:
#   * the debounce key holds a token that every signal overwrites, naming the
#     newest state that still needs exporting;
#   * the pending key marks that a task is already queued, so the signals that
#     follow only update the token.
# A queued task waits EXPORT_DEBOUNCE_DELAY seconds, drops the pending marker,
# and exports only if its token is still current. If newer signals arrived it
# queues itself again with the newer token instead, so the export reflects the
# end of the burst rather than a mid-import snapshot. A missing debounce entry
# (e.g. evicted) exports anyway rather than silently dropping the export.
EXPORT_DEBOUNCE_DELAY = 5  # seconds of quiet before a queued export actually runs
EXPORT_DEBOUNCE_CACHE_KEY = "git_export_debounce:{content_key}"
EXPORT_DEBOUNCE_PENDING_CACHE_KEY = "git_export_pending:{content_key}"
# Outlives the countdown so the marker can't expire while the task is still
# waiting in the broker, but short enough that a task lost with its worker
# only delays the next export by a minute.
EXPORT_DEBOUNCE_PENDING_TTL = 60  # seconds
