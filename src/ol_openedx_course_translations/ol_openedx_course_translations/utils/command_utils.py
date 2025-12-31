"""
Utility functions for management commands.

This module provides reusable utilities for Django management commands,
including validation, error handling, git operations, and configuration helpers.
"""

import os
import re
from datetime import UTC, datetime
from typing import Any

from django.conf import settings
from django.core.management.base import CommandError

# ============================================================================
# Validation Utilities
# ============================================================================


def validate_language_code(code: str, field_name: str = "language code") -> None:
    """Validate language code format (xx or xx_XX)."""
    if not re.match(r"^[a-z]{2}(_[A-Z]{2})?$", code):
        msg = (
            f"Invalid {field_name} format: {code}. "
            f"Expected format: 'xx' or 'xx_XX' (e.g., 'el', 'es_ES')"
        )
        raise CommandError(msg)


def validate_branch_name(branch_name: str) -> None:
    """Validate branch name format to prevent injection."""
    if not re.match(r"^[a-z0-9/_-]+$", branch_name):
        msg = f"Invalid branch name format: {branch_name}"
        raise CommandError(msg)


# ============================================================================
# Git Utilities
# ============================================================================


def sanitize_for_git(text: str) -> str:
    """Sanitize text for use in git operations."""
    return re.sub(r"[^\w\s-]", "", text)


def create_branch_name(lang_code: str) -> str:
    """Create a safe branch name from language code."""
    safe_lang = re.sub(r"[^a-z0-9_-]", "", lang_code.lower())
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"feature/add-{safe_lang}-translations-{timestamp}"


# ============================================================================
# Configuration Helpers
# ============================================================================


def get_config_value(key: str, options: dict, default: Any = None) -> Any:
    """Get configuration value from options, settings, or environment."""
    if options.get(key):
        return options[key]
    setting_key = key.upper().replace("-", "_")
    if hasattr(settings, setting_key):
        return getattr(settings, setting_key)
    env_key = setting_key
    return os.environ.get(env_key, default)


# ============================================================================
# Error Handling Utilities
# ============================================================================


def is_retryable_error(error: Exception) -> bool:
    """
    Check if an error is retryable (network issues, rate limits, timeouts).

    Args:
        error: The exception to check

    Returns:
        True if the error is retryable, False otherwise

    Examples:
        >>> is_retryable_error(ConnectionError("Connection timeout"))
        True
        >>> is_retryable_error(ValueError("Invalid API key"))
        False
    """
    error_str = str(error).lower()

    # Retryable errors
    retryable_patterns = [
        "timeout",
        "connection",
        "rate limit",
        "429",
        "503",
        "502",
        "500",
        "temporarily unavailable",
        "service unavailable",
        "too many requests",
    ]

    # Non-retryable errors (don't retry these)
    non_retryable_patterns = [
        "invalid api key",
        "authentication",
        "401",
        "403",
        "not found",
        "404",
        "bad request",
        "400",
        "commanderror",  # Our custom errors that are usually non-retryable
    ]

    # Check for non-retryable first
    for pattern in non_retryable_patterns:
        if pattern in error_str:
            return False

    # Check for retryable patterns
    for pattern in retryable_patterns:
        if pattern in error_str:
            return True

    # Default: retry unknown errors (could be transient)
    return True
