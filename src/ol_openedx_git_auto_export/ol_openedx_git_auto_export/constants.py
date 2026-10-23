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

# A publish burst fires one signal per block. The pending key keeps one export
# task queued per burst; the debounce key holds a token every signal overwrites.
# A task exports only while its token is current, else it re-queues -- so the
# export reflects the end of the burst. A missing token counts as current.
EXPORT_DEBOUNCE_DELAY = 5  # seconds of quiet before the export happens
# v2: reusing the unversioned key would make a rollback see it as already
# claimed by the new long-lived token, and silently stop debouncing.
EXPORT_DEBOUNCE_CACHE_KEY = "git_export_debounce_v2:{content_key}"
EXPORT_DEBOUNCE_PENDING_CACHE_KEY = "git_export_pending:{content_key}"
# Must outlive the countdown plus broker/worker pickup, or a duplicate queues.
EXPORT_DEBOUNCE_PENDING_TTL = EXPORT_DEBOUNCE_DELAY + 55  # seconds
# Bounded so dormant content doesn't sit in the cache forever.
EXPORT_DEBOUNCE_TOKEN_TTL = 60 * 60 * 24 * 7  # 7 days
# A burst that keeps postponing its export is exported anyway after this long.
EXPORT_MAX_WAIT = 10 * 60  # seconds
EXPORT_BURST_START_CACHE_KEY = "git_export_burst_start:{content_key}"
# Must outlive the max wait plus one hop, or the burst forgets when it began.
EXPORT_BURST_START_TTL = EXPORT_MAX_WAIT + EXPORT_DEBOUNCE_PENDING_TTL

# Exports of one content item share a clone directory, so they serialize on
# this lock. Celery kills an export at EXPORT_TIME_LIMIT, before the lock
# expires, so a lock never lapses under a running export.
EXPORT_TIME_LIMIT = 10 * 60  # seconds
EXPORT_LOCK_CACHE_KEY = "git_export_lock:{content_key}"
EXPORT_LOCK_TTL = EXPORT_TIME_LIMIT + 60  # seconds
# git holds index.lock for seconds; an older one was left by a killed process.
STALE_GIT_LOCK_AGE = 60  # seconds
