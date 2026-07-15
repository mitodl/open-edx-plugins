"""Minimal standalone Django settings for ol_openedx_sentry tests.

These settings allow the test suite to run without a full edx-platform
install.  The plugin only needs a minimal Django app configuration.
"""

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "ol_openedx_sentry",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
SECRET_KEY = "test-secret-key-not-for-production"  # noqa: S105  # pragma: allowlist secret
DEBUG = False
