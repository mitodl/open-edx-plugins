ENABLE_GIT_AUTO_EXPORT = "ENABLE_GIT_AUTO_EXPORT"
ENABLE_AUTO_GITHUB_REPO_CREATION = "ENABLE_AUTO_GITHUB_REPO_CREATION"
GITHUB_ORG = "GITHUB_ORG"
GITHUB_ACCESS_TOKEN = "GITHUB_ACCESS_TOKEN"  # noqa: S105

COURSE_RERUN_STATE_SUCCEEDED = "succeeded"
REPOSITORY_NAME_MAX_LENGTH = 100  # Max length from GitHub for repo name

# Per-course git export distributed lock settings.
# The pending task's total wait budget (MAX_RETRIES * RETRY_DELAY) must exceed
# the lock TTL so a pending task cannot exhaust its retries while the running
# export is still in progress.
EXPORT_LOCK_TIMEOUT = 120  # seconds; safety TTL if a worker crashes holding the lock
EXPORT_LOCK_RETRY_DELAY = 30  # seconds between retries for the pending task
EXPORT_LOCK_MAX_RETRIES = 5  # max retries for the pending task
# At most one extra task queues behind the running task; all other duplicates drop.
EXPORT_PENDING_TIMEOUT = EXPORT_LOCK_TIMEOUT  # match the lock TTL

# Cache key templates for the distributed git-export lock.
EXPORT_LOCK_CACHE_KEY = "git_export_lock:{course_key}"
EXPORT_PENDING_CACHE_KEY = "git_export_pending:{course_key}"
