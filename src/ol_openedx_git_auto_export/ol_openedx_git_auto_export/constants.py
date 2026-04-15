ENABLE_GIT_AUTO_EXPORT = "ENABLE_GIT_AUTO_EXPORT"
ENABLE_AUTO_GITHUB_REPO_CREATION = "ENABLE_AUTO_GITHUB_REPO_CREATION"
GITHUB_ORG = "GITHUB_ORG"
GITHUB_ACCESS_TOKEN = "GITHUB_ACCESS_TOKEN"  # noqa: S105

COURSE_RERUN_STATE_SUCCEEDED = "succeeded"
REPOSITORY_NAME_MAX_LENGTH = 100  # Max length from GitHub for repo name

# Debounce settings for the signal handler.
# A single course save triggers 10-30 COURSE_PUBLISHED signals in one request.
# cache.add() on this key ensures only the first signal schedules a task; all
# subsequent signals within the window are silently dropped before hitting the broker.
# The task is scheduled with countdown=EXPORT_DEBOUNCE_DELAY so it runs after
# the burst window has closed and the course state is fully settled.
EXPORT_DEBOUNCE_DELAY = 5  # seconds — must exceed the publish burst window
EXPORT_DEBOUNCE_CACHE_KEY = "git_export_debounce:{course_key}"
