"""Minimal standalone Django settings for ol_openedx_logging tests.

These settings allow the test suite to run without a full edx-platform
install.  The logging plugin is self-contained, so only a minimal Django
app configuration is required.
"""

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "ol_openedx_logging",
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

# Minimal edX-style LOGGING with a tracking handler so tests can verify
# it is preserved by configure_structlog().
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "raw": {"format": "%(message)s"},
    },
    "handlers": {
        "tracking": {
            "level": "DEBUG",
            "class": "logging.handlers.MemoryHandler",
            "capacity": 100,
            "formatter": "raw",
        }
    },
    "loggers": {
        "tracking": {
            "handlers": ["tracking"],
            "level": "DEBUG",
            "propagate": False,
        }
    },
}
