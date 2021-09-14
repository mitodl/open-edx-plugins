from typing import Any, Dict

MEGABYTE = 1024 * 1024


def _load_env_tokens(edx_settings, default_settings: Dict[str, Any]) -> Dict[str, Any]:
    configured_tokens = getattr(edx_settings, "ENV_TOKENS", {})
    default_settings.update(configured_tokens)
    return default_settings


def plugin_settings(edx_settings):
    env_tokens = _load_env_tokens(
        edx_settings,
        {
            "EDXAPP_LOG_LEVEL": "INFO",
            "EDXAPP_LOG_FILE_PATH": "/var/log/edxapp/app.log",
            "EDXAPP_LOG_FILE_MAX_MEGABYTES": 10,
        },
    )
    edx_logging = getattr(edx_settings, "LOGGING", {})
    edx_log_level = env_tokens["EDXAPP_LOG_LEVEL"]

    edx_logging["formatters"]["json_format"] = {
        "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
        "timestamp": True,
        "reserved_attrs": [],  # Add all log attributes to JSON object
    }

    edx_logging["handlers"]["file"] = {
        "level": edx_log_level,
        "class": "logging.handlers.RotatingFileHandler",
        "filename": env_tokens["EDXAPP_LOG_FILE_PATH"],
        "formatter": "json_format",
        "backupCount": 3,
        "mode": "a",
        "maxBytes": MEGABYTE * env_tokens["EDXAPP_LOG_FILE_MAX_MEGABYTES"],
    }

    edx_logging["loggers"][""] = {
        "handlers": ["console", "local", "file"],
        "level": edx_log_level,
        "propagate": False,
    }

    edx_settings.LOGGING = edx_logging
