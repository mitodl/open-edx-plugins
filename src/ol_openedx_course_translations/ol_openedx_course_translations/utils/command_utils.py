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
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    return f"feature/add-{safe_lang}-translations-{timestamp}"


# ============================================================================
# Configuration Helpers
# ============================================================================


def get_config_value(key: str, options: dict, default: Any = None) -> Any:
    """Get configuration value from options, settings, or environment."""
    # Check command-line options first (Django converts --repo-path to repo_path)
    option_value = options.get(key) or options.get(key.replace("_", "-"))
    if option_value:
        return option_value

    # Check settings with TRANSLATIONS_ prefix
    setting_key = f"TRANSLATIONS_{key.upper().replace('-', '_')}"
    if hasattr(settings, setting_key):
        setting_value = getattr(settings, setting_key)
        # Only use setting if it's not empty
        if setting_value:
            return setting_value

    # Check environment variable with TRANSLATIONS_ prefix
    env_key = setting_key
    env_value = os.environ.get(env_key)
    if env_value:
        return env_value

    # Return default if nothing found
    return default


def get_default_provider() -> str | None:
    """Get default provider from TRANSLATIONS_PROVIDERS."""
    providers = getattr(settings, "TRANSLATIONS_PROVIDERS", {})
    if not isinstance(providers, dict):
        return None
    return providers.get("default_provider")


def get_default_model_for_provider(provider: str) -> str | None:
    """Get default model for a provider from TRANSLATIONS_PROVIDERS."""
    providers = getattr(settings, "TRANSLATIONS_PROVIDERS", {})
    if not isinstance(providers, dict):
        return None
    provider_config = providers.get(provider, {})
    if not isinstance(provider_config, dict):
        return None
    return provider_config.get("default_model")


def configure_litellm_for_provider(
    provider: str, model: str, api_key: str | None, **base_kwargs
) -> dict[str, Any]:
    """Configure LiteLLM completion kwargs for a specific provider."""
    completion_kwargs = dict(base_kwargs)
    completion_kwargs["model"] = model

    if api_key:
        completion_kwargs["api_key"] = api_key
        if provider == "gemini":
            if not model.startswith(("gemini/", "vertex_ai/")):
                completion_kwargs["model"] = f"gemini/{model}"
            # Gemini 3 models require temperature = 1.0 to avoid issues
            if "gemini-3" in model.lower():
                completion_kwargs["temperature"] = 1.0
        elif provider == "mistral" and not model.startswith("mistral/"):
            completion_kwargs["model"] = f"mistral/{model}"

    return completion_kwargs


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
