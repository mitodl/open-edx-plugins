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

# A course save or library import fires many publish signals for the same
# content, up to one per block. The pending key keeps a single export task
# queued per burst; the debounce key holds a token every signal overwrites.
# The task exports only if its token is still current, otherwise it re-queues
# itself, so the export reflects the end of the burst. If the debounce cache
# entry itself is gone (evicted/expired), the task treats itself as current
# and exports rather than dropping the export.
EXPORT_DEBOUNCE_DELAY = 5  # seconds of quiet before a queued export actually runs
# v2: 0.8.3 wrote a 5s-TTL "1" under the unversioned key. Storing the new,
# much longer-lived token there instead (see EXPORT_DEBOUNCE_TOKEN_TTL below)
# would make a rollback to 0.8.3 see that key as already claimed, silently
# disabling its debounce until the token expires.
EXPORT_DEBOUNCE_CACHE_KEY = "git_export_debounce_v2:{content_key}"
EXPORT_DEBOUNCE_PENDING_CACHE_KEY = "git_export_pending:{content_key}"
# Must outlive the countdown, or the marker expires while the task is still
# queued and a signal in that gap queues a duplicate.
EXPORT_DEBOUNCE_PENDING_TTL = EXPORT_DEBOUNCE_DELAY + 55  # seconds
# Bounded, not permanent: a course/library that's never published again would
# otherwise leave its token in the cache forever. A missing/expired token is
# already treated as current (see the comment above), so this is safe to
# expire -- it only needs to comfortably outlive any realistic gap between
# signals in one publish burst, not the content's whole lifetime.
EXPORT_DEBOUNCE_TOKEN_TTL = 60 * 60 * 24 * 7  # 7 days
