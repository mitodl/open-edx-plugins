"""
Django management command to sync translation keys, translate using LLM, and create PRs.

Usage:
    ./manage.py cms sync_and_translate_language el
    ./manage.py cms sync_and_translate_language el \\
        --provider openai --model gpt-4-turbo --glossary
"""

import json
import logging
import os
import re
import shutil
import subprocess
import textwrap
import time
import urllib.parse
from configparser import NoSectionError
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any, TypedDict, cast

import git
import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from litellm import completion

import ol_openedx_course_translations.utils.translation_sync as utils_module
from ol_openedx_course_translations.utils.command_utils import (
    configure_litellm_for_provider,
    create_branch_name,
    get_config_value,
    get_default_model_for_provider,
    get_default_provider,
    is_retryable_error,
    normalize_language_code,
    sanitize_for_git,
    validate_branch_name,
    validate_language_code,
)
from ol_openedx_course_translations.utils.constants import (
    HTTP_CREATED,
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTP_TOO_MANY_REQUESTS,
    HTTP_UNPROCESSABLE_ENTITY,
    LANGUAGE_MAPPING,
    MAX_ERROR_MESSAGE_LENGTH,
    MAX_LOG_ICU_STRING_LENGTH,
    MAX_LOG_STRING_LENGTH,
    MAX_RETRIES,
    PLURAL_CATEGORIES_ARABIC,
    PLURAL_CATEGORIES_FOUR,
    PLURAL_CATEGORIES_THREE,
    PLURAL_CATEGORIES_TWO,
    PLURAL_FORMS,
    PROVIDER_GEMINI,
    PROVIDER_MISTRAL,
)
from ol_openedx_course_translations.utils.translation_sync import (
    _get_base_lang,
    apply_json_translations,
    apply_po_translations,
    extract_empty_keys,
    load_glossary,
    match_glossary_term,
    sync_all_translations,
)

logger = logging.getLogger(__name__)


class GitRepository:
    """Helper class for git operations with consistent error handling."""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        try:
            self.repo = git.Repo(repo_path)
        except git.exc.InvalidGitRepositoryError as e:
            msg = (
                f"Invalid git repository at {repo_path}. "
                f"Please remove it or specify a different path."
            )
            raise CommandError(msg) from e
        except git.exc.GitCommandError as e:
            msg = f"Git error accessing repository: {e!s}"
            raise CommandError(msg) from e

    def _handle_git_error(self, operation: str, error: Exception) -> None:
        """Convert git errors to CommandError with context."""
        msg = f"Git error {operation}: {error!s}"
        raise CommandError(msg) from error

    def _get_main_branch_name(self) -> str:
        """
        Determine the main branch name.
        Checks local branches first, then remote branches.
        Fetches from remote if needed to check remote branches.
        """
        # Check if 'main' exists locally
        if "main" in [ref.name for ref in self.repo.heads]:
            return "main"

        # If not found locally, fetch from remote and check remote branches
        with suppress(git.exc.GitCommandError):
            # If fetch fails, we'll try to check existing remote refs anyway
            self.repo.remotes.origin.fetch()

        # Check remote branches
        if "origin/main" in [ref.name for ref in self.repo.remotes.origin.refs]:
            return "main"

        msg = "Main branch not found locally or on remote"
        raise CommandError(msg)

    def ensure_clean(self) -> bool:
        """
        Clean uncommitted changes in tracked files.
        Returns True if cleaned, False if already clean.

        This ensures any leftover staged/uncommitted changes from a previous
        interrupted run are removed before starting a new translation sync.
        """
        try:
            if self.repo.is_dirty(untracked_files=False):
                self.repo.head.reset(index=True, working_tree=True)
                return True
            else:
                return False
        except git.exc.GitCommandError as e:
            self._handle_git_error("cleaning repository", e)
            return False  # Never reached, but satisfies type checker

    def switch_to_main(self) -> None:
        """Switch to main branch, deleting current branch if it's not main."""
        try:
            # Get current branch name (might be in detached HEAD state)
            try:
                current_branch = self.repo.active_branch.name
            except TypeError:
                # Detached HEAD state - we'll checkout main anyway
                current_branch = None

            # Get the main branch name
            main_branch = self._get_main_branch_name()

            # Only switch if we're not already on the main branch
            if current_branch != main_branch:
                # Try to checkout the branch (will work if it exists locally)
                try:
                    self.repo.git.checkout(main_branch)
                except git.exc.GitCommandError:
                    # Branch doesn't exist locally, checkout from remote
                    self.repo.git.checkout("-b", main_branch, f"origin/{main_branch}")

                # Delete the previous branch if it exists and is not the main branch
                if current_branch and current_branch != main_branch:
                    with suppress(git.exc.GitCommandError):
                        self.repo.git.branch("-D", current_branch)
        except (git.exc.GitCommandError, TypeError) as e:
            self._handle_git_error("switching branches", e)

    def update_from_remote(self) -> None:
        """Fetch and pull latest changes from origin/main."""
        try:
            self.repo.remotes.origin.fetch()
            main_branch = self._get_main_branch_name()
            self.repo.git.pull("origin", main_branch)
        except git.exc.GitCommandError as e:
            self._handle_git_error("updating repository", e)

    def get_remote_url(self) -> str | None:
        """Get the current remote URL."""
        try:
            return self.repo.remotes.origin.url
        except (git.exc.GitCommandError, AttributeError):
            return None

    def configure_user(
        self,
        email: str = "translations@mitodl.org",
        name: str = "MIT Open Learning Translations Bot",
    ) -> None:
        """Configure git user for this repository."""
        try:
            with self.repo.config_writer() as config:
                # Check if user section exists and get existing values
                try:
                    existing_email = config.get_value("user", "email", default=None)
                    existing_name = config.get_value("user", "name", default=None)
                except NoSectionError:
                    # Section doesn't exist, set both values
                    existing_email = None
                    existing_name = None
                # Set values only if they don't exist
                if not existing_email:
                    config.set_value("user", "email", email)
                if not existing_name:
                    config.set_value("user", "name", name)
        except git.exc.GitCommandError as e:
            self._handle_git_error("configuring user", e)

    def branch_exists(self, branch_name: str) -> bool:
        """Check if branch exists locally or remotely."""
        validate_branch_name(branch_name)
        try:
            # Check local branches
            if branch_name in [ref.name for ref in self.repo.heads]:
                return True
            # Check remote branches
            remote_branch = f"origin/{branch_name}"
            try:
                self.repo.remotes.origin.fetch()
            except git.exc.GitCommandError:
                # If fetch fails, try to check existing remote refs anyway
                # Check remote refs with existing data
                return remote_branch in [
                    ref.name for ref in self.repo.remotes.origin.refs
                ]
            else:
                # Fetch succeeded, check remote refs
                return remote_branch in [
                    ref.name for ref in self.repo.remotes.origin.refs
                ]
        except git.exc.GitCommandError as e:
            self._handle_git_error("checking branch existence", e)
            return False  # Never reached, but satisfies type checker

    def create_branch(self, branch_name: str) -> None:
        """Create and checkout a new branch."""
        validate_branch_name(branch_name)
        try:
            self.repo.git.checkout("-b", branch_name)
        except git.exc.GitCommandError as e:
            self._handle_git_error("creating branch", e)

    def stage_all(self) -> None:
        """Stage all changes."""
        try:
            self.repo.git.add(".")
        except git.exc.GitCommandError as e:
            self._handle_git_error("staging changes", e)

    def has_changes(self) -> bool:
        """Check if there are uncommitted changes."""
        try:
            return self.repo.is_dirty(untracked_files=True)
        except git.exc.GitCommandError as e:
            self._handle_git_error("checking changes", e)
            return False  # Never reached, but satisfies type checker

    def commit(self, message: str) -> None:
        """Commit staged changes."""
        try:
            self.repo.index.commit(message)
        except git.exc.GitCommandError as e:
            self._handle_git_error("committing changes", e)

    @contextmanager
    def authenticated_push_url(self, github_token: str):
        """Context manager for authenticated push with automatic cleanup."""
        origin = self.repo.remotes.origin
        original_url = origin.url

        # Build authenticated URL
        match = re.search(r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?$", original_url)
        if match:
            owner, repo_name = match.groups()
            encoded_token = urllib.parse.quote(github_token, safe="")
            push_url = f"https://{encoded_token}@github.com/{owner}/{repo_name}.git"
        else:
            encoded_token = urllib.parse.quote(github_token, safe="")
            push_url = original_url.replace("https://", f"https://{encoded_token}@")

        try:
            origin.set_url(push_url)
            yield
        finally:
            # Always restore original URL
            try:
                origin.set_url(original_url)
            except (git.exc.GitCommandError, ValueError) as e:
                # Best effort cleanup - log but don't fail
                logger.warning("Failed to restore original git remote URL: %s", e)

    def push_branch(self, branch_name: str, github_token: str | None = None) -> None:
        """Push branch to remote with optional authentication."""
        validate_branch_name(branch_name)
        try:
            if github_token:
                with self.authenticated_push_url(github_token):
                    self.repo.git.push("-u", "origin", branch_name)
            else:
                self.repo.git.push("-u", "origin", branch_name)
        except git.exc.GitCommandError as e:
            self._handle_git_error("pushing branch", e)

    @staticmethod
    def clone(repo_url: str, repo_path: str) -> "GitRepository":
        """Clone a repository and return GitRepository instance."""
        repo_path_obj = Path(repo_path)
        try:
            repo_path_obj.parent.mkdir(parents=True, exist_ok=True)
            git.Repo.clone_from(repo_url, str(repo_path))
            return GitRepository(repo_path)
        except git.exc.GitCommandError as e:
            msg = f"Git error cloning repository: {e!s}"
            raise CommandError(msg) from e
        except OSError as e:
            msg = f"Error creating directory: {e!s}"
            raise CommandError(msg) from e


class GitHubAPIClient:
    """Helper class for GitHub API operations."""

    def __init__(self, token: str | None = None):
        """Initialize with optional token."""
        self.token = (
            token
            or getattr(settings, "TRANSLATIONS_GITHUB_TOKEN", None)
            or os.environ.get("TRANSLATIONS_GITHUB_TOKEN")
        )
        if not self.token:
            msg = "TRANSLATIONS_GITHUB_TOKEN not set in settings or environment"
            raise CommandError(msg)

    def _get_headers(self) -> dict:
        """Get API request headers."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        }

    @staticmethod
    def parse_repo_url(repo_url: str) -> tuple[str, str]:
        """Extract owner and repo from GitHub URL."""
        match = re.search(r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?$", repo_url)
        if not match:
            msg = f"Could not parse owner/repo from repo URL: {repo_url}"
            raise CommandError(msg)
        owner, repo = match.groups()
        return (owner, repo)

    def _handle_rate_limit(
        self, response: requests.Response, attempt: int, max_retries: int, stdout
    ) -> bool:
        """Handle rate limit response. Returns True if should retry."""
        if response.status_code == HTTP_TOO_MANY_REQUESTS:
            retry_after = int(response.headers.get("Retry-After", 2 * (2**attempt)))
            if attempt < max_retries - 1:
                stdout.write(
                    f"   Rate limit exceeded (attempt {attempt + 1}/{max_retries}). "
                    f"Retrying in {retry_after} seconds..."
                )
                time.sleep(retry_after)
                return True
            else:
                msg = "GitHub API rate limit exceeded. Please try again later."
                raise CommandError(msg)
        return False

    def _extract_error_message(self, response: requests.Response) -> str:
        """Extract safe error message from response, including validation errors."""
        try:
            error_data = response.json()
            message = error_data.get("message", f"HTTP {response.status_code}")

            # GitHub API validation errors include detailed error info in 'errors' array
            if error_data.get("errors"):
                error_details = []
                for err in error_data["errors"]:
                    if isinstance(err, dict):
                        field = err.get("field", "unknown")
                        code = err.get("code", "unknown")
                        resource = err.get("resource", "unknown")
                        error_details.append(f"{resource}.{field}: {code}")
                    else:
                        error_details.append(str(err))

                if error_details:
                    message = f"{message} ({', '.join(error_details)})"
                return message
            else:
                return message
        except (ValueError, requests.exceptions.JSONDecodeError):
            return f"HTTP {response.status_code}"

    def verify_branch(
        self,
        owner: str,
        repo: str,
        branch_name: str,
        stdout,  # noqa: ARG002
    ) -> None:
        """Verify branch exists on remote."""
        url = f"https://api.github.com/repos/{owner}/{repo}/branches/{branch_name}"
        response = requests.get(url, headers=self._get_headers(), timeout=10)

        if response.status_code == HTTP_NOT_FOUND:
            msg = (
                f"Branch '{branch_name}' not found on remote. "
                f"Ensure the branch was pushed successfully."
            )
            raise CommandError(msg)
        elif response.status_code != HTTP_OK:
            error_msg = self._extract_error_message(response)
            msg = f"Failed to verify branch: {error_msg}"
            raise CommandError(msg)
        # If status_code is HTTP_OK, function returns None implicitly

    def create_pull_request(  # noqa: PLR0913
        self,
        owner: str,
        repo: str,
        branch_name: str,
        title: str,
        body: str,
        base: str = "main",
        stdout=None,
    ) -> str:
        """Create a pull request with retry logic."""
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        payload = {"title": title, "body": body, "head": branch_name, "base": base}
        headers = self._get_headers()

        max_retries = 3
        base_retry_delay = 2

        for attempt in range(max_retries):
            retry_delay = base_retry_delay * (2**attempt)

            try:
                response = requests.post(url, json=payload, headers=headers, timeout=30)

                if response.status_code == HTTP_CREATED:
                    return response.json()["html_url"]

                if self._handle_rate_limit(
                    response, attempt, max_retries, stdout or self
                ):
                    continue

                if response.status_code == HTTP_UNPROCESSABLE_ENTITY:
                    error_msg = self._extract_error_message(response)
                    safe_error = (
                        error_msg[:MAX_ERROR_MESSAGE_LENGTH]
                        if len(error_msg) > MAX_ERROR_MESSAGE_LENGTH
                        else error_msg
                    )
                    msg = (
                        f"GitHub API validation error: {safe_error}\n"
                        f"This usually means the branch doesn't exist on remote "
                        f"or there's already a PR for this branch."
                    )
                    raise CommandError(msg)

                error_msg = self._extract_error_message(response)
                safe_error = (
                    error_msg[:MAX_ERROR_MESSAGE_LENGTH]
                    if len(error_msg) > MAX_ERROR_MESSAGE_LENGTH
                    else error_msg
                )
                msg = f"GitHub API error: {safe_error}"
                raise CommandError(msg)

            except requests.exceptions.RequestException as e:
                is_connection_error = isinstance(
                    e,
                    (requests.exceptions.ConnectionError, requests.exceptions.Timeout),
                )

                if is_connection_error and attempt < max_retries - 1:
                    if stdout:
                        error_msg = (
                            f"   Connection error "
                            f"(attempt {attempt + 1}/{max_retries}): {e!s}"
                        )
                        stdout.write(error_msg)
                        stdout.write(f"   Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    continue
                else:
                    if is_connection_error:
                        msg = (
                            f"Failed to connect to GitHub API after "
                            f"{max_retries} attempts: {e!s}\n"
                            f"Please check your network connection and try again later."
                        )
                        raise CommandError(msg) from e
                    msg = f"GitHub API error: {e!s}"
                    raise CommandError(msg) from e

        msg = "Failed to create pull request after all retries"
        raise CommandError(msg)


class PullRequestData(TypedDict):
    """Data structure for pull request creation."""

    lang_code: str
    iso_code: str
    sync_stats: dict
    applied_count: int
    translation_stats: dict[str, Any]
    applied_by_app: dict[str, Any]
    provider: str
    model: str


class TranslationParams(TypedDict):
    """Parameters for translation operations."""

    lang_code: str
    provider: str
    model: str
    glossary: dict[str, Any] | None
    batch_size: int
    max_retries: int


class Command(BaseCommand):
    help = (
        "Sync translation keys, translate using LLM, "
        "and create PR in mitxonline-translations"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "lang", type=str, help="Language code (e.g., el, fr, es_ES)"
        )
        parser.add_argument(
            "--iso-code",
            type=str,
            help="ISO code for JSON files (default: same as lang)",
        )
        parser.add_argument(
            "--repo-path",
            type=str,
            help=(
                "Path to mitxonline-translations repository. "
                "Can also be set via TRANSLATIONS_REPO_PATH setting "
                "or environment variable."
            ),
        )
        default_provider = get_default_provider()
        parser.add_argument(
            "--provider",
            type=str,
            default=default_provider,
            choices=["openai", "gemini", "mistral"],
            help=(
                "Translation provider (openai, gemini, mistral). "
                "Default is taken from TRANSLATIONS_PROVIDERS['default_provider']"
                + (
                    f" (currently: {default_provider})"
                    if default_provider
                    else " (not configured)"
                )
            ),
        )
        parser.add_argument(
            "--model",
            type=str,
            default=None,
            help=(
                "Model name (e.g., gpt-4, gemini-pro, mistral-large-latest). "
                "If not specified, uses the default_model for the selected provider "
                "from TRANSLATIONS_PROVIDERS. "
                "LiteLLM automatically detects provider from model name."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run without committing or creating PR",
        )
        parser.add_argument(
            "--glossary",
            action="store_true",
            default=False,
            help="Use glossary from plugin glossaries folder. "
            "Looks for {plugin_dir}/glossaries/machine_learning/{iso_code}.txt "
            "(uses --iso-code when given, else lang code).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=200,
            help=(
                "Number of keys to translate per API request (default: 200). "
                "Larger batches are faster but may hit rate limits. "
                "Recommended: 200-300 for most models, "
                "up to 400-500 for large models like mistral-large."
            ),
        )
        parser.add_argument(
            "--mfe",
            type=str,
            nargs="+",
            help=(
                "Filter by specific MFE(s). "
                "Use 'edx-platform' for backend translations."
            ),
        )
        parser.add_argument(
            "--repo-url",
            type=str,
            help=(
                "GitHub repository URL. "
                "Can also be set via TRANSLATIONS_REPO_URL setting "
                "or environment variable."
            ),
        )

    def handle(self, *args, **options):  # noqa: ARG002, PLR0915
        """Handle the command execution."""
        # Normalize language codes (convert hyphens to underscores)
        lang_code = normalize_language_code(options["lang"])
        iso_code = normalize_language_code(options.get("iso_code") or lang_code)

        validate_language_code(lang_code)
        validate_language_code(iso_code, "ISO code")

        repo_path = get_config_value(
            "repo_path",
            options,
            str(Path.home() / ".mitxonline-translations"),
        )
        repo_url = get_config_value(
            "repo_url",
            options,
            "https://github.com/mitodl/mitxonline-translations.git",
        )

        # Validate repository path is not empty
        if not repo_path or not repo_path.strip():
            msg = (
                "Repository path is not set. Please specify --repo-path, "
                "set TRANSLATIONS_REPO_PATH in Django settings, or set "
                "TRANSLATIONS_REPO_PATH environment variable."
            )
            raise CommandError(msg)

        self.stdout.write(self.style.SUCCESS(f"Processing language: {lang_code}"))
        self.stdout.write(f"   ISO code: {iso_code}")
        self.stdout.write(f"   Repository: {repo_path}")

        repo = self._ensure_repo(repo_path, repo_url)

        self.stdout.write("\nSyncing translation keys...")
        base_dir = Path(repo_path) / "translations"
        sync_stats = sync_all_translations(
            base_dir, lang_code, iso_code, skip_backend=False
        )
        self._log_sync_stats(sync_stats)

        # Extract and filter empty keys
        self.stdout.write("\nExtracting empty keys for translation...")
        empty_keys = extract_empty_keys(
            base_dir, lang_code, iso_code, skip_backend=False
        )
        empty_keys = self._filter_by_mfe(empty_keys, options.get("mfe"))

        if not empty_keys:
            self.stdout.write(self.style.SUCCESS("\nNo empty keys to translate!"))
            return

        glossary = self._load_glossary(options, iso_code)

        provider = options.get("provider") or get_default_provider()
        if not provider:
            msg = (
                "Provider not specified and "
                "TRANSLATIONS_PROVIDERS['default_provider'] is not set"
            )
            raise CommandError(msg)

        model = options.get("model") or get_default_model_for_provider(provider)
        if not model:
            msg = (
                f"Model not specified and provider '{provider}' "
                "does not have default_model in TRANSLATIONS_PROVIDERS"
            )
            raise CommandError(msg)

        self.stdout.write(f"\nTranslating using {provider}/{model}...")
        params = TranslationParams(
            lang_code=lang_code,
            provider=provider,
            model=model,
            glossary=glossary,
            batch_size=options.get("batch_size", 200),
            max_retries=MAX_RETRIES,
        )
        translations, translation_stats = self._translate_keys(empty_keys, params)
        self.stdout.write(f"   Translated {len(translations)} keys")

        self.stdout.write("\nApplying translations...")
        applied_count, applied_by_app = self._apply_translations(
            translations, empty_keys, self.stdout
        )
        self.stdout.write(f"   Applied {applied_count} translations")

        if options.get("dry_run"):
            self.stdout.write(self.style.WARNING("\nDry run - no changes committed"))
            return

        branch_name = create_branch_name(lang_code)
        self.stdout.write(f"\nCommitting changes to branch: {branch_name}")

        if not self._commit_changes(repo, branch_name, lang_code):
            return

        self.stdout.write("\nCreating pull request...")
        try:
            pr_data = PullRequestData(
                lang_code=lang_code,
                iso_code=iso_code,
                sync_stats=sync_stats,
                applied_count=applied_count,
                translation_stats=translation_stats,
                applied_by_app=applied_by_app,
                provider=provider,
                model=model,
            )
            pr_url = self._create_pull_request(
                repo_path,
                branch_name,
                pr_data,
                repo_url,
            )
            self.stdout.write(self.style.SUCCESS(f"\nPull request created: {pr_url}"))
        except CommandError as e:
            # Clean up branch if PR creation fails
            self.stdout.write(
                self.style.ERROR(f"\nFailed to create pull request: {e!s}")
            )
            self._cleanup_failed_branch(repo, branch_name)
            raise

    def _ensure_repo(self, repo_path: str, repo_url: str) -> GitRepository:
        """Ensure repository exists and is ready. Returns GitRepository instance."""
        repo_path_obj = Path(repo_path)
        is_git_repo = repo_path_obj.exists() and (repo_path_obj / ".git").exists()

        if is_git_repo:
            repo = GitRepository(repo_path)
            current_url = repo.get_remote_url()

            # Normalize URLs for comparison (remove .git suffix, trailing slashes)
            normalized_current = (current_url or "").rstrip(".git").rstrip("/")
            normalized_new = repo_url.rstrip(".git").rstrip("/")

            # If URL changed, delete and re-clone
            if normalized_current != normalized_new:
                self.stdout.write(
                    self.style.WARNING(
                        f"   Repository URL changed from {current_url} to {repo_url}"
                    )
                )
                self.stdout.write("   Removing old repository and cloning new one...")
                shutil.rmtree(repo_path)
                self.stdout.write(f"   Cloning repository to {repo_path}...")
                repo = GitRepository.clone(repo_url, repo_path)
                self.stdout.write(
                    self.style.SUCCESS("   Repository cloned successfully")
                )
                return repo

            # URL matches, use existing repo
            self.stdout.write(f"   Repository found at {repo_path}")
            if repo.ensure_clean():
                self.stdout.write(
                    self.style.WARNING(
                        "   WARNING: Found uncommitted changes (cleaned up)"
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS("   Cleaned up uncommitted changes")
                )

            repo.switch_to_main()
            self.stdout.write("   Updating repository...")
            repo.update_from_remote()
            self.stdout.write(self.style.SUCCESS("   Repository up to date"))
            return repo

        elif repo_path_obj.exists():
            msg = (
                f"Path {repo_path} exists but is not a git repository. "
                f"Please remove it or specify a different path."
            )
            raise CommandError(msg)
        else:
            self.stdout.write(f"   Cloning repository to {repo_path}...")
            repo = GitRepository.clone(repo_url, repo_path)
            self.stdout.write(self.style.SUCCESS("   Repository cloned successfully"))
            return repo

    def _log_sync_stats(self, sync_stats: dict) -> None:
        """Log synchronization statistics."""
        self.stdout.write(
            f"   Frontend: {sync_stats['frontend']['added']} keys added, "
            f"{sync_stats['frontend']['fixed']} typos fixed"
        )
        self.stdout.write(f"   Backend: {sync_stats['backend']['added']} entries added")

    def _filter_by_mfe(
        self, empty_keys: list[dict], mfe_filter: list[str] | None
    ) -> list[dict]:
        """Filter empty keys by MFE if specified."""
        if not mfe_filter:
            self.stdout.write(f"   Found {len(empty_keys)} empty keys")
            return empty_keys

        mfe_set = set(mfe_filter)
        original_count = len(empty_keys)
        available_apps = {key.get("app", "unknown") for key in empty_keys}
        filtered = [key for key in empty_keys if key.get("app") in mfe_set]

        if not filtered:
            mfe_list = ", ".join(mfe_filter)
            apps_list = ", ".join(sorted(available_apps))
            self.stdout.write(
                self.style.WARNING(
                    f"\nWARNING: No empty keys found for specified MFE(s): "
                    f"{mfe_list}\n"
                    f"   Available apps: {apps_list}"
                )
            )
            return []

        mfe_list = ", ".join(mfe_filter)
        self.stdout.write(
            f"   Filtered to {len(filtered)} keys from {len(mfe_set)} MFE(s): "
            f"{mfe_list} (was {original_count} total)"
        )
        return filtered

    def _get_icu_plural_categories(self, lang_code: str) -> list[str]:
        """Get ICU MessageFormat plural categories for a language."""
        base_lang = _get_base_lang(lang_code)
        plural_form = PLURAL_FORMS.get(base_lang, "nplurals=2; plural=(n != 1);")

        nplurals_match = re.search(r"nplurals=(\d+)", plural_form)
        if not nplurals_match:
            return ["one", "other"]

        nplurals = int(nplurals_match.group(1))

        # Map nplurals to ICU categories
        nplurals_to_categories = {
            1: ["other"],
            2: ["one", "other"],
            3: ["one", "few", "other"],
            4: ["one", "two", "few", "other"],
            6: ["zero", "one", "two", "few", "many", "other"],
        }

        return nplurals_to_categories.get(nplurals, ["one", "other"])

    def _get_po_plural_count(self, lang_code: str) -> int:
        """Get number of plural forms for a language (for PO files)."""
        base_lang = _get_base_lang(lang_code)
        plural_form = PLURAL_FORMS.get(base_lang, "nplurals=2; plural=(n != 1);")

        nplurals_match = re.search(r"nplurals=(\d+)", plural_form)
        if not nplurals_match:
            return 2

        return int(nplurals_match.group(1))

    def _build_icu_example(self, categories_list: list[str]) -> str:
        """Build an ICU MessageFormat example string based on categories."""
        num_categories = len(categories_list)

        if num_categories == PLURAL_CATEGORIES_ARABIC:
            # Arabic: zero, one, two, few, many, other
            return (
                "{activityCount, plural, "
                "zero {# activities} "
                "one {# activity} "
                "two {# activities} "
                "few {# activities} "
                "many {# activities} "
                "other {# activities}}"
            )
        elif num_categories == PLURAL_CATEGORIES_FOUR:
            # Languages with 4 forms: one, two, few, other
            return (
                "{activityCount, plural, "
                "one {# activity} "
                "two {# activities} "
                "few {# activities} "
                "other {# activities}}"
            )
        elif num_categories == PLURAL_CATEGORIES_THREE:
            # Languages with 3 forms: one, few, other (e.g., Russian, Polish)
            return (
                "{activityCount, plural, "
                "one {# activity} "
                "few {# activities} "
                "other {# activities}}"
            )
        elif num_categories == PLURAL_CATEGORIES_TWO:
            # Languages with 2 forms: one, other (most languages)
            return "{activityCount, plural, one {# activity} other {# activities}}"
        else:
            # Fallback for other multi-category languages
            example_categories = " ".join(
                f"{cat} {{# {'activity' if cat == 'one' else 'activities'}}}"
                for cat in categories_list
            )
            return f"{{activityCount, plural, {example_categories}}}"

    def _load_glossary(self, options: dict, iso_code: str) -> dict[str, Any]:
        """Load glossary if enabled. Uses ISO code for file lookup.

        iso_code is already normalized (e.g. es_419). Tries {iso_code}.txt first,
        then {iso_code with underscores→hyphens}.txt (e.g. es-419.txt) if not found.
        """
        if not options.get("glossary", False):
            return {}

        utils_file = Path(utils_module.__file__)
        base_dir = utils_file.parent.parent / "glossaries" / "machine_learning"
        candidates = [
            base_dir / f"{iso_code}.txt",
            base_dir / f"{iso_code.replace('_', '-')}.txt",
        ]
        glossary_path = None
        for path in candidates:
            if path.exists():
                glossary_path = path
                break

        if glossary_path is not None:
            self.stdout.write(f"\nLoading glossary from {glossary_path}...")
            glossary = load_glossary(glossary_path, iso_code)
            self.stdout.write(f"   Loaded {len(glossary)} glossary terms")
            return glossary

        self.stdout.write(
            self.style.WARNING(
                f"\nWARNING: Glossary file not found for {iso_code} "
                f"(tried {candidates[0].name}, {candidates[1].name})\n"
                f"   Continuing without glossary."
            )
        )
        return {}

    def _check_glossary_for_keys(
        self,
        empty_keys: list[dict],
        glossary: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], int, list[dict]]:
        """Check glossary matches for keys.

        Returns (translations, matches_count, remaining_keys).
        """
        translations = {}
        glossary_matches = 0
        keys_needing_llm = []

        for key_info in empty_keys:
            # Normalize file path for consistent comparison
            file_path_str = str(Path(key_info["file_path"]).resolve())
            # Include msgctxt in key if it exists to distinguish entries with same msgid
            msgctxt = key_info.get("msgctxt")
            if msgctxt:
                translation_key = f"{file_path_str}:{msgctxt}:{key_info['key']}"
            else:
                translation_key = f"{file_path_str}:{key_info['key']}"

            if glossary:
                match_result = self._check_glossary_match(key_info, glossary)
                if match_result:
                    translations[translation_key] = match_result
                    glossary_matches += 1
                    continue

            keys_needing_llm.append(key_info)

        return translations, glossary_matches, keys_needing_llm

    def _process_batch_results(
        self,
        batch: list[dict],
        batch_translations: list[Any],
        translations: dict[str, Any],
    ) -> tuple[int, int, dict[str, int]]:
        """Process batch translation results.

        Returns (successes, errors, errors_by_app).
        """
        batch_successes = 0
        batch_errors = 0
        batch_errors_by_app: dict[str, int] = {}

        for i, key_info in enumerate(batch):
            # Normalize file path for consistent comparison
            file_path_str = str(Path(key_info["file_path"]).resolve())
            # Include msgctxt in key if it exists to distinguish entries with same msgid
            msgctxt = key_info.get("msgctxt")
            if msgctxt:
                translation_key = f"{file_path_str}:{msgctxt}:{key_info['key']}"
            else:
                translation_key = f"{file_path_str}:{key_info['key']}"
            app = key_info.get("app", "unknown")
            if i < len(batch_translations) and batch_translations[i]:
                translations[translation_key] = batch_translations[i]
                batch_successes += 1
            else:
                batch_errors += 1
                batch_errors_by_app[app] = batch_errors_by_app.get(app, 0) + 1

        return batch_successes, batch_errors, batch_errors_by_app

    def _translate_with_llm(  # noqa: PLR0913
        self,
        keys_needing_llm: list[dict],
        translations: dict[str, Any],
        lang_code: str,
        provider: str,
        model: str,
        glossary: dict[str, Any] | None,
        batch_size: int,
        max_retries: int,
    ) -> tuple[int, int, dict[str, int]]:
        """Translate keys using LLM with batch processing.

        Returns (llm_translations, llm_errors, errors_by_app).
        """
        llm_translations = 0
        llm_errors = 0
        errors_by_app: dict[str, int] = {}

        total_keys = len(keys_needing_llm)
        num_batches = (total_keys + batch_size - 1) // batch_size
        self.stdout.write(
            f"   Translating {total_keys} keys using LLM "
            f"({num_batches} batches of up to {batch_size} keys each)..."
        )

        for batch_idx, batch in enumerate(
            [
                keys_needing_llm[i : i + batch_size]
                for i in range(0, total_keys, batch_size)
            ],
            1,
        ):
            batch_succeeded = False
            batch_apps = {key_info.get("app", "unknown") for key_info in batch}

            # Retry loop for this batch
            for attempt in range(max_retries + 1):  # +1 for initial attempt
                try:
                    batch_translations = self._call_llm_batch(
                        batch, lang_code, provider, model, glossary
                    )
                    batch_successes, batch_errors, batch_errors_by_app = (
                        self._process_batch_results(
                            batch,
                            batch_translations,
                            translations,
                        )
                    )

                    llm_translations += batch_successes
                    llm_errors += batch_errors
                    for app, count in batch_errors_by_app.items():
                        errors_by_app[app] = errors_by_app.get(app, 0) + count

                    completed = min(batch_idx * batch_size, total_keys)
                    progress_pct = min((completed / total_keys) * 100, 100)
                    remaining_keys = total_keys - llm_translations

                    self._log_batch_progress(
                        batch_idx,
                        num_batches,
                        batch_successes,
                        batch_errors,
                        completed,
                        total_keys,
                        progress_pct,
                        remaining_keys,
                        batch_apps,
                        batch_errors_by_app,
                        attempt,
                    )

                    batch_succeeded = True
                    break  # Success - exit retry loop

                except (
                    requests.RequestException,
                    ValueError,
                    KeyError,
                    AttributeError,
                ) as e:
                    if not self._handle_batch_error(
                        e, batch_idx, num_batches, batch_apps, attempt, max_retries
                    ):
                        break  # Non-retryable error

            # If batch failed after all retries, mark all keys as errors
            if not batch_succeeded:
                batch_errors = len(batch)
                llm_errors += batch_errors
                for key_info in batch:
                    app = key_info.get("app", "unknown")
                    errors_by_app[app] = errors_by_app.get(app, 0) + 1
                apps_str = ", ".join(sorted(batch_apps))
                self.stdout.write(
                    self.style.ERROR(
                        f"         Marked {batch_errors} keys as errors, "
                        f"continuing with next batch...\n"
                        f"         Affected apps: {apps_str}"
                    )
                )

        return llm_translations, llm_errors, errors_by_app

    def _log_batch_progress(  # noqa: PLR0913
        self,
        batch_idx: int,
        num_batches: int,
        batch_successes: int,
        batch_errors: int,
        completed: int,
        total_keys: int,
        progress_pct: float,
        remaining_keys: int,
        batch_apps: set[str],
        batch_errors_by_app: dict[str, int],
        attempt: int,
    ) -> None:
        """Log batch processing progress."""
        retry_msg = f" (after {attempt + 1} attempt(s))" if attempt > 0 else ""
        if batch_errors > 0:
            apps_str = ", ".join(sorted(batch_apps))
            errors_by_app_str = ", ".join(
                f"{app}: {count}" for app, count in sorted(batch_errors_by_app.items())
            )
            self.stdout.write(
                f"   Batch {batch_idx}/{num_batches} completed "
                f"with partial success "
                f"({batch_successes} succeeded, "
                f"{batch_errors} failed){retry_msg} "
                f"({completed}/{total_keys} keys, "
                f"{progress_pct:.1f}% complete, "
                f"{remaining_keys} remaining)\n"
                f"         Affected apps: {apps_str}\n"
                f"         Errors by app: {errors_by_app_str}"
            )
        else:
            self.stdout.write(
                f"   Batch {batch_idx}/{num_batches} completed"
                f"{retry_msg} "
                f"({completed}/{total_keys} keys, "
                f"{progress_pct:.1f}% complete, "
                f"{remaining_keys} remaining)"
            )

    def _handle_batch_error(  # noqa: PLR0913
        self,
        error: Exception,
        batch_idx: int,
        num_batches: int,
        batch_apps: set[str],
        attempt: int,
        max_retries: int,
    ) -> bool:
        """Handle batch error. Returns True if should retry, False otherwise."""
        apps_str = ", ".join(sorted(batch_apps))
        if not is_retryable_error(error):
            # Non-retryable error - fail immediately
            self.stdout.write(
                self.style.ERROR(
                    f"   ERROR: Batch {batch_idx}/{num_batches} "
                    f"failed with non-retryable error: {error!s}\n"
                    f"         Affected apps: {apps_str}"
                )
            )
            return False

        # Retryable error - check if we have retries left
        if attempt < max_retries:
            # Exponential backoff: 2^attempt seconds (1s, 2s, 4s, 8s...)
            wait_time = 2**attempt
            self.stdout.write(
                self.style.WARNING(
                    f"   WARNING: Batch {batch_idx}/{num_batches} "
                    f"failed (attempt {attempt + 1}/"
                    f"{max_retries + 1}): {error!s}\n"
                    f"         Affected apps: {apps_str}\n"
                    f"         Retrying in {wait_time} second(s)..."
                )
            )
            time.sleep(wait_time)
            return True
        else:
            # Out of retries
            self.stdout.write(
                self.style.ERROR(
                    f"   ERROR: Batch {batch_idx}/{num_batches} "
                    f"failed after {max_retries + 1} attempts: "
                    f"{error!s}\n"
                    f"         Affected apps: {apps_str}"
                )
            )
            return False

    def _translate_keys(
        self,
        empty_keys: list[dict],
        params: TranslationParams,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Translate empty keys using LLM with batch processing."""
        lang_code = params["lang_code"]
        provider = params["provider"]
        model = params["model"]
        glossary = params["glossary"]
        batch_size = params["batch_size"]

        # Add lang_code to each key_info for ICU format conversion
        for key_info in empty_keys:
            key_info["lang_code"] = lang_code
        max_retries = params["max_retries"]

        # First pass: check glossary matches
        logger.info(
            "Checking glossary matches for %d empty key(s) (language: %s)",
            len(empty_keys),
            lang_code,
        )
        translations, glossary_matches, keys_needing_llm = (
            self._check_glossary_for_keys(empty_keys, glossary)
        )

        logger.info(
            "Glossary matches: %d, Keys needing LLM: %d",
            glossary_matches,
            len(keys_needing_llm),
        )

        if not keys_needing_llm:
            logger.info("All translations found in glossary, skipping LLM translation")
            return translations, {
                "glossary_matches": glossary_matches,
                "llm_translations": 0,
                "errors": 0,
                "errors_by_app": cast("dict[str, int]", {}),
            }

        # Translate remaining keys with LLM
        logger.info(
            "Starting LLM translation for %d key(s) using %s/%s (batch size: %d)",
            len(keys_needing_llm),
            provider,
            model,
            batch_size,
        )
        llm_translations, llm_errors, errors_by_app = self._translate_with_llm(
            keys_needing_llm,
            translations,
            lang_code,
            provider,
            model,
            glossary,
            batch_size,
            max_retries,
        )
        logger.info(
            "LLM translation completed: %d translated, %d errors",
            llm_translations,
            llm_errors,
        )

        summary = (
            f"   Summary - LLM translations: {llm_translations}, Errors: {llm_errors}"
        )
        if glossary:
            summary = (
                f"   Summary - Glossary matches: {glossary_matches}, {summary[12:]}"
            )
        self.stdout.write(summary)

        return translations, {
            "glossary_matches": glossary_matches,
            "llm_translations": llm_translations,
            "errors": llm_errors,
            "errors_by_app": errors_by_app,
        }

    def _check_glossary_match(
        self, key_info: dict, glossary: dict[str, Any] | None
    ) -> Any | None:
        """
        Check if key matches glossary. Returns translation or None.

        Args:
            key_info: Dictionary containing key information with 'english',
                'is_plural', etc.
            glossary: Dictionary mapping English terms to translations, or None.

        Returns:
            Translation string/dict if match found, None otherwise.
        """
        if not glossary:
            return None

        is_plural = key_info.get("is_plural", False)
        msgid_plural = key_info.get("msgid_plural")

        if is_plural and msgid_plural:
            return self._check_plural_glossary_match(key_info, glossary, msgid_plural)

        match = match_glossary_term(key_info["english"], glossary, exact_match=True)
        if not match:
            logger.debug(
                "No glossary match found for key: %s", key_info.get("key", "unknown")
            )
            return None

        translation = (
            match.get("translation", match.get("singular", ""))
            if isinstance(match, dict)
            else match
        )
        logger.debug(
            "Found glossary match for key: %s -> %s",
            key_info.get("key", "unknown"),
            str(translation)[:MAX_LOG_STRING_LENGTH] + "..."
            if len(str(translation)) > MAX_LOG_STRING_LENGTH
            else str(translation),
        )
        return translation

    def _is_icu_format(self, text: str) -> bool:
        """Check if text is already in ICU MessageFormat."""
        if not isinstance(text, str):
            return False
        # Match ICU MessageFormat pattern: {variable, plural, ...}
        icu_pattern = r"\{[^,]+,\s*plural\s*,"
        return bool(re.search(icu_pattern, text))

    def _convert_to_icu_format(
        self, singular: str, plural: str, lang_code: str, count_var: str = "count"
    ) -> str:
        """Convert singular and plural translations to ICU MessageFormat string."""
        categories = self._get_icu_plural_categories(lang_code)

        parts = [f"{{{count_var}, plural"]
        for category in categories:
            translation = singular if category == "one" else plural
            parts.append(f" {category} {{{translation}}}")
        parts.append("}")

        icu_string = "".join(parts)
        logger.debug(
            "Converted singular/plural to ICU format for %s: %s (categories: %s)",
            lang_code,
            (
                icu_string[:MAX_LOG_ICU_STRING_LENGTH] + "..."
                if len(icu_string) > MAX_LOG_ICU_STRING_LENGTH
                else icu_string
            ),
            categories,
        )
        return icu_string

    def _extract_translation_from_match(self, match: Any) -> str:
        """Extract translation string from glossary match."""
        if isinstance(match, str):
            return match
        return match.get(
            "singular", match.get("plural", match.get("translation", str(match)))
        )

    def _check_plural_glossary_match(
        self, key_info: dict, glossary: dict[str, Any], msgid_plural: str
    ) -> Any | None:
        """Check glossary match for plural keys. Returns translation or None."""
        file_type = key_info.get("file_type", "po")
        singular_match = match_glossary_term(
            key_info["english"], glossary, exact_match=True
        )
        plural_match = match_glossary_term(msgid_plural, glossary, exact_match=True)

        if singular_match and plural_match:
            singular_str = self._extract_translation_from_match(singular_match)
            plural_str = self._extract_translation_from_match(plural_match)

            if file_type == "json":
                lang_code = key_info.get("lang_code", "en")
                return self._convert_to_icu_format(singular_str, plural_str, lang_code)

            return {"singular": singular_str, "plural": plural_str}

        if singular_match:
            key_info["_glossary_singular"] = self._extract_translation_from_match(
                singular_match
            )

        return None

    def _format_glossary_for_prompt(self, glossary: dict[str, Any] | None) -> str:
        """Format glossary as a prompt section for LLM translation requests.

        Args:
            glossary: Dictionary mapping English terms to translations, or
                None/empty dict.

        Returns:
            Empty string if glossary is None or empty, otherwise returns a
            formatted string with glossary terms and instructions for consistent
            translation.
        """
        if not glossary:
            return ""

        try:
            glossary_json = json.dumps(glossary, indent=2, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            self.stdout.write(
                self.style.WARNING(
                    f"   WARNING: Could not serialize glossary for prompt: {e!s}. "
                    f"Continuing without glossary in LLM prompt."
                )
            )
            return ""
        glossary_template = f"""
            IMPORTANT - Use these glossary terms when translating. If any English terms
            from the glossary appear in the texts to translate, use the corresponding
            translation from the glossary:

            {glossary_json}

            When translating sentences, ensure that glossary terms are translated
            consistently according to the glossary above, even if they appear
            within longer sentences. For example, if the glossary specifies
            "certificate" -> "Πιστοποιητικό", then translate "certificate" as
            "Πιστοποιητικό" even when it appears in longer sentences like
            "The course completion certificate is available".
            """
        return textwrap.dedent(glossary_template)

    def _build_plural_instructions(
        self,
        json_plural_info: dict[str, Any],
        plural_count: int,
        key_batch: list[dict],
        icu_categories_str: str,
        lang_code: str,
    ) -> str:
        """Build plural handling instructions for LLM prompt."""
        instructions = []
        json_plural_count = json_plural_info.get("count", 0)
        json_plural_entries = json_plural_info.get("entries", {})

        if json_plural_count > 0:
            categories_list = icu_categories_str.split(", ")
            num_categories = len(categories_list)
            has_existing_icu = any(
                self._is_icu_format(key_batch[i].get("english", ""))
                for i in range(len(key_batch))
                if str(i + 1) in json_plural_entries
            )

            if has_existing_icu:
                if num_categories > PLURAL_CATEGORIES_TWO:
                    # For languages with multiple plural forms (e.g., Arabic with 6),
                    # expand the ICU structure to include ALL required categories
                    instructions.append(
                        f"IMPORTANT: {json_plural_count} entry/entries are JSON "
                        f"strings with ICU MessageFormat plural forms. "
                        f"These may currently have only 'one' and 'other' "
                        f"categories, but for this language ({icu_categories_str}), "
                        f"you MUST expand them to include ALL {num_categories} "
                        f"categories: {icu_categories_str}. "
                        f"Translate the content and return a complete ICU "
                        f"MessageFormat string with ALL categories. "
                        f"Example format: {{count, plural, {icu_categories_str} "
                        f"{{translation}} ... other {{translation}}}}. "
                        f"CRITICAL: Do not preserve the existing 2-category "
                        f"structure. Expand it to include all {num_categories} "
                        f"required categories for this language."
                    )
                else:
                    # For languages with 2 forms, preserve existing structure
                    instructions.append(
                        f"IMPORTANT: {json_plural_count} entry/entries are JSON "
                        f"strings with ICU MessageFormat plural forms. "
                        f"These already have the ICU structure "
                        f"(e.g., {{activityCount, plural, one {{# activity}} "
                        f"other {{# activities}}}}). "
                        f"Translate the content inside the plural forms while "
                        f"preserving the exact ICU structure and variable names. "
                        f"Return the complete ICU MessageFormat string with "
                        f"translated content."
                    )
            else:
                # Build language-specific example based on categories
                example = self._build_icu_example(categories_list)

                if num_categories > PLURAL_CATEGORIES_TWO:
                    instructions.append(
                        f"IMPORTANT: {json_plural_count} entry/entries are for "
                        f"JSON files with plural forms. "
                        f"For these, return ICU MessageFormat strings with ALL "
                        f"plural categories: {icu_categories_str}. "
                        f"Format: {{count, plural, {icu_categories_str} "
                        f"{{translation}} ... other {{translation}}}}. "
                        f"Example: {example}. "
                        f"IMPORTANT: Include ALL {num_categories} categories in "
                        f"your response, not just 'one' and 'other'. Each category "
                        f"may require different word forms in this language."
                    )
                else:
                    instructions.append(
                        f"IMPORTANT: {json_plural_count} entry/entries are for "
                        f"JSON files with plural forms. "
                        f"For these, return ICU MessageFormat strings with plural "
                        f"categories: {icu_categories_str}. "
                        f"Format: {{count, plural, {icu_categories_str} "
                        f"{{translation}} ... other {{translation}}}}. "
                        f"Example: {example}."
                    )

        if plural_count > 0:
            # Get number of plural forms needed for this language
            po_plural_count = self._get_po_plural_count(lang_code)
            if po_plural_count > PLURAL_CATEGORIES_TWO:
                # Languages with more than 2 forms need all forms translated
                instructions.append(
                    f"CRITICAL - PO FILE PLURAL ENTRIES "
                    f"({plural_count} entry/entries): "
                    f"These are for PO files (NOT JSON files). "
                    f"This language requires {po_plural_count} plural forms "
                    f"(indices 0, 1, 2, ..., {po_plural_count - 1}). "
                    f"For PO files, you MUST return an object with keys "
                    f"'0', '1', '2', ..., '{po_plural_count - 1}', "
                    f"covering all indices from 0 through "
                    f"{po_plural_count - 1}, where each value is a "
                    f"PLAIN TRANSLATION STRING. "
                    f"\n"
                    f"WRONG (DO NOT DO THIS): "
                    f"{{'0': '{{count, plural, one {{...}} other {{...}}}}'}} "
                    f"\n"
                    f"CORRECT: "
                    f"{{'0': 'translation for zero items', "
                    f"'1': 'translation for one item', "
                    f"'2': 'translation for two items', "
                    f"'3': 'translation for few items', "
                    f"'4': 'translation for many items', "
                    f"'5': 'translation for other items'}} "
                    f"\n"
                    f"Each value must be a simple translated string, "
                    f"NOT ICU MessageFormat syntax. "
                    f"Preserve placeholders like {{count}}, %(count)s, etc. "
                    f"in the plain strings."
                )
            else:
                # Languages with 2 forms use singular/plural format
                instructions.append(
                    f"CRITICAL - PO FILE PLURAL ENTRIES "
                    f"({plural_count} entry/entries): "
                    f"These are for PO files (NOT JSON files). "
                    f"For PO files, return an object with 'singular' and "
                    f"'plural' keys, each containing a PLAIN TRANSLATION STRING. "
                    f"\n"
                    f"WRONG (DO NOT DO THIS): "
                    f"{{'singular': '{{count, plural, one {{...}} "
                    f"other {{...}}}}'}} "
                    f"\n"
                    f"CORRECT: "
                    f"{{'singular': 'translation for one item', "
                    f"'plural': 'translation for multiple items'}} "
                    f"\n"
                    f"Each value must be a simple translated string, "
                    f"NOT ICU MessageFormat syntax. "
                    f"Preserve placeholders like {{count}}, %(count)s, etc. "
                    f"in the plain strings."
                )

        return "\n".join(instructions)

    def _call_llm_batch(  # noqa: PLR0913
        self,
        key_batch: list[dict],
        lang_code: str,
        provider: str,
        model: str,
        glossary: dict[str, Any] | None = None,
        timeout: int = 120,
    ) -> list[str | dict[str, str] | None]:
        """Call LLM API to translate multiple texts in a single request.

        Args:
            key_batch: List of key information dictionaries to translate
            lang_code: Target language code
            provider: Translation provider name (openai, gemini, mistral)
            model: LLM model name
            glossary: Optional glossary dictionary
            timeout: Request timeout in seconds (default: 120)
        """
        api_key = self._get_llm_api_key(provider)

        texts_dict = {}
        plural_entries: dict[str, bool] = {}
        json_plural_entries: dict[str, bool] = {}

        for i, key_info in enumerate(key_batch, 1):
            key_str = str(i)
            file_type = key_info.get("file_type", "po")
            english_text = key_info["english"]
            is_plural = key_info.get("is_plural", False)
            msgid_plural = key_info.get("msgid_plural")

            if file_type == "json" and self._is_icu_format(english_text):
                texts_dict[key_str] = english_text
                json_plural_entries[key_str] = True
            elif is_plural and msgid_plural:
                texts_dict[key_str] = {"singular": english_text, "plural": msgid_plural}
                (json_plural_entries if file_type == "json" else plural_entries)[
                    key_str
                ] = True
            else:
                texts_dict[key_str] = english_text

        texts_block = json.dumps(texts_dict, indent=2, ensure_ascii=False)
        plural_count = len(plural_entries)
        json_plural_count = len(json_plural_entries)

        lang_name = LANGUAGE_MAPPING.get(lang_code, lang_code)
        glossary_section = self._format_glossary_for_prompt(glossary)
        icu_categories_str = ", ".join(self._get_icu_plural_categories(lang_code))
        plural_instructions = self._build_plural_instructions(
            {"count": json_plural_count, "entries": json_plural_entries},
            plural_count,
            key_batch,
            icu_categories_str,
            lang_code,
        )

        prompt_template = (
            f"""Translate the following {len(key_batch)} text(s) to {lang_name} """
            f"""(language code: {lang_code}).
            Context: These are from an educational platform.
            Preserve any placeholders like {{variable}}, {{0}}, %s, etc.
            Preserve HTML tags and formatting.
            {glossary_section}
            {plural_instructions}

            Return a JSON object where each key is the number (1, 2, 3, etc.).

            FORMAT BY ENTRY TYPE:

            1. Singular entries (no plural): value is a simple translation string.

            2. JSON plural entries: value is an ICU MessageFormat string.
               Example: "{{count, plural, one {{# item}} other {{# items}}}}"

            3. PO plural entries: value is an object with PLAIN TRANSLATION STRINGS.
               NEVER use ICU MessageFormat for PO entries!
               Use simple translated strings for each form.

               For languages with 2 forms:
                 {{"singular": "translation for one", "plural": "translation for many"}}

               For languages with more forms (e.g., Arabic with 6):
                 {{"0": "translation for zero", "1": "translation for one",
                   "2": "translation for two", "3": "translation for few",
                   "4": "translation for many", "5": "translation for other"}}

               CRITICAL: Each value in PO entries must be a plain string, "
               "NOT ICU syntax! Preserve placeholders ({{count}}, "
               "%(count)s, etc.) in the plain strings.

            Input texts (numbered):
            {texts_block}

            Return ONLY valid JSON in this format:
            {{
              "1": "translation of first text",
              "2": "{{count, plural, one {{singular}} "
              "other {{plural}}}}",
              "3": {{"singular": "singular translation", "
              ""plural": "plural translation"}},
              "4": {{"0": "form 0", "1": "form 1", "2": "form 2"}}
              ...
            }}"""
        )
        prompt = textwrap.dedent(prompt_template)

        try:
            completion_kwargs = configure_litellm_for_provider(
                provider=provider,
                model=model,
                api_key=api_key,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                timeout=timeout,
            )

            response = completion(**completion_kwargs)
            response_text = response.choices[0].message.content.strip()

            logger.debug(
                "LLM response received for batch of %d key(s), response length: %d",
                len(key_batch),
                len(response_text),
            )

            translations = self._parse_json_response(response_text, key_batch)
            if translations:
                logger.debug(
                    "Successfully parsed JSON response for batch of %d key(s)",
                    len(key_batch),
                )
                return translations

            logger.warning(
                "JSON parsing failed for batch, falling back to order-based parsing"
            )
            return self._parse_order_based_response(response_text, key_batch)

        except TimeoutError:
            logger.exception(
                "LLM batch API call timed out after %d seconds "
                "(model: %s, batch size: %d)",
                timeout,
                model,
                len(key_batch),
            )
            msg = (
                f"LLM batch API call timed out after {timeout} seconds.\n"
                f"Model: {model}\n"
                f"Batch size: {len(key_batch)}\n"
                f"Try reducing --batch-size or check your network connection."
            )
            raise CommandError(msg) from None
        except (requests.RequestException, ValueError, KeyError, AttributeError) as e:
            logger.exception(
                "LLM batch API call failed (model: %s, batch size: %d)",
                model,
                len(key_batch),
            )
            msg = (
                f"LLM batch API call failed: {e!s}\n"
                f"Model: {model}\n"
                f"Batch size: {len(key_batch)}\n"
                f"Make sure TRANSLATIONS_PROVIDERS is configured in settings "
                f"with the appropriate api_key, or set the environment variable "
                f"(OPENAI_API_KEY, GEMINI_API_KEY, or MISTRAL_API_KEY)"
            )
            raise CommandError(msg) from e

    def _extract_json_from_response(self, response_text: str) -> str:
        """Extract JSON text from response, handling code blocks."""
        json_text = response_text
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            if end > start:
                json_text = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            if end > start:
                json_text = response_text[start:end].strip()
        return json_text

    def _process_translation_key(
        self, key: str, value: Any, key_info: dict
    ) -> tuple[str | dict[str, str] | None, bool]:
        """Process a single translation key from LLM response."""
        file_type = key_info.get("file_type", "po")
        is_plural = key_info.get("is_plural", False)

        translation = self._process_llm_response_value(
            value, key_info, file_type, is_plural=is_plural
        )
        is_missing = translation is None

        if translation is None:
            self._log_rejected_translation(key, key_info)
        elif translation is not None:
            self._log_parsed_translation(key_info, translation)

        return translation, is_missing

    def _log_rejected_translation(self, key: str, key_info: dict) -> None:
        """Log warning for rejected translation."""
        self.stdout.write(
            self.style.WARNING(
                f"   WARNING: Translation rejected for key {key} "
                f"(file: {key_info.get('file_path', 'unknown')}, "
                f"key: {key_info.get('key', 'unknown')[:50]}). "
                f"Likely returned ICU format for PO file."
            )
        )
        logger.warning(
            "Translation rejected for key %s (file: %s) - "
            "likely ICU format for PO file",
            key_info.get("key", "unknown"),
            key_info.get("file_path", "unknown"),
        )

    def _log_parsed_translation(
        self, key_info: dict, translation: str | dict[str, str]
    ) -> None:
        """Log debug message for parsed translation."""
        logger.debug(
            "Parsed translation for key %s: %s",
            key_info.get("key", "unknown"),
            (
                str(translation)[:MAX_LOG_STRING_LENGTH] + "..."
                if len(str(translation)) > MAX_LOG_STRING_LENGTH
                else str(translation)
            ),
        )

    def _parse_json_response(
        self, response_text: str, key_batch: list[dict]
    ) -> list[str | dict[str, str] | None] | None:
        """Parse JSON response from LLM."""
        json_text = self._extract_json_from_response(response_text)

        try:
            data = json.loads(json_text)
            translations: list[str | dict[str, str] | None] = []
            missing_keys = []
            for i in range(len(key_batch)):
                key = str(i + 1)
                key_info = key_batch[i]

                if key in data:
                    value = data[key]
                    translation, is_missing = self._process_translation_key(
                        key, value, key_info
                    )
                    if is_missing:
                        missing_keys.append(key_info.get("key", "unknown"))
                    translations.append(translation)
                else:
                    missing_keys.append(key_info.get("key", "unknown"))
                    self.stdout.write(
                        self.style.WARNING(
                            f"   WARNING: LLM did not return translation for key {key} "
                            f"(file: {key_info.get('file_path', 'unknown')}, "
                            f"key: {key_info.get('key', 'unknown')})"
                        )
                    )
                    logger.warning(
                        "LLM did not return translation for key %s (file: %s)",
                        key_info.get("key", "unknown"),
                        key_info.get("file_path", "unknown"),
                    )
                    translations.append(None)

            if missing_keys:
                logger.warning(
                    "LLM response missing %d key(s): %s",
                    len(missing_keys),
                    missing_keys,
                )
        except (json.JSONDecodeError, KeyError, ValueError):
            logger.exception("Failed to parse JSON response")
            return None
        else:
            return translations

    def _parse_order_based_response(
        self, response_text: str, key_batch: list[dict]
    ) -> list[str | dict[str, str] | None]:
        """Fallback: Parse response assuming translations are in order."""
        lines = [line.strip() for line in response_text.split("\n") if line.strip()]
        cleaned_lines = [
            line.lstrip("0123456789.-) ").strip()
            for line in lines
            if line.lstrip("0123456789.-) ").strip()
        ]
        if len(cleaned_lines) < len(key_batch):
            cleaned_lines.extend([""] * (len(key_batch) - len(cleaned_lines)))
        # Return as list[str | dict[str, str] | None] - all strings in this fallback
        return cast(
            "list[str | dict[str, str] | None]", cleaned_lines[: len(key_batch)]
        )

    def _get_llm_api_key(self, provider: str) -> str | None:
        """Get API key from TRANSLATIONS_PROVIDERS or environment variables.

        Args:
            provider: Translation provider name (openai, gemini, mistral)
        """
        try:
            if hasattr(settings, "TRANSLATIONS_PROVIDERS"):
                providers = getattr(settings, "TRANSLATIONS_PROVIDERS", {})
                if isinstance(providers, dict) and provider in providers:
                    provider_config = providers[provider]
                    if isinstance(provider_config, dict):
                        api_key = provider_config.get("api_key")
                        if api_key:
                            return api_key
        except (AttributeError, TypeError) as e:
            logger.debug("Error accessing TRANSLATIONS_PROVIDERS: %s", e)

        env_key_name = (
            "GEMINI_API_KEY"
            if provider == PROVIDER_GEMINI
            else "MISTRAL_API_KEY"
            if provider == PROVIDER_MISTRAL
            else "OPENAI_API_KEY"
        )
        return os.environ.get(env_key_name)

    def _process_string_value(
        self, value: str, file_type: str, *, is_plural: bool
    ) -> tuple[str | dict | None, bool]:
        """Process a string value from LLM response.

        Returns:
            Tuple of (result, is_dict) where is_dict indicates if result is a dict
            that should be processed further.
        """
        stripped = value.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return self._parse_string_dict(stripped, file_type, is_plural=is_plural)
        if self._is_icu_format(stripped):
            if file_type == "po" and is_plural:
                return None, False
            return stripped, False
        return stripped, False

    def _parse_string_dict(
        self, value: str, file_type: str, *, is_plural: bool
    ) -> tuple[str | dict | None, bool]:
        """Parse a string that looks like a dict."""
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                # Return dict to be processed further
                return parsed, True
        except (json.JSONDecodeError, ValueError):
            # Not valid JSON; fall through to ICU check and plain string handling.
            pass

        # Not a dict or parsing failed, check ICU format
        if self._is_icu_format(value) and file_type == "po" and is_plural:
            return None, False
        return value, False

    def _process_dict_numeric_keys(
        self, value: dict, file_type: str, *, is_plural: bool
    ) -> dict[str, str] | None:
        """Process dict with numeric keys (multiple plural forms)."""
        numeric_keys = [
            k for k in value if (isinstance(k, (int, str)) and str(k).isdigit())
        ]
        if not numeric_keys or file_type != "po" or not is_plural:
            return None

        result = {}
        for k, v in value.items():
            if isinstance(k, (int, str)) and str(k).isdigit():
                v_str = str(v).strip()
                if self._is_icu_format(v_str):
                    return None
                result[str(k)] = v_str
        return result if result else None

    def _process_dict_singular_plural(
        self, value: dict, key_info: dict, file_type: str, *, is_plural: bool
    ) -> str | dict[str, str] | None:
        """Process dict with singular/plural keys."""
        if "singular" not in value or "plural" not in value:
            return None

        if file_type == "json" and is_plural:
            lang_code = key_info.get("lang_code", "en")
            return self._convert_to_icu_format(
                str(value["singular"]).strip(),
                str(value["plural"]).strip(),
                lang_code,
            )
        return {
            "singular": str(value["singular"]).strip(),
            "plural": str(value["plural"]).strip(),
        }

    def _process_llm_response_value(
        self, value: Any, key_info: dict, file_type: str, *, is_plural: bool
    ) -> str | dict[str, str] | None:
        """Process a single value from LLM response, converting formats."""
        if isinstance(value, str):
            result, is_dict = self._process_string_value(
                value, file_type, is_plural=is_plural
            )
            if result is None:
                return None
            if is_dict:
                # Result is a dict, process it further
                value = result
            else:
                # Result is a string, return it
                return result

        if isinstance(value, dict):
            # Check for numeric keys (multiple plural forms)
            result = self._process_dict_numeric_keys(
                value, file_type, is_plural=is_plural
            )
            if result is not None:
                return result

            # Check for singular/plural format
            result = self._process_dict_singular_plural(
                value, key_info, file_type, is_plural=is_plural
            )
            if result is not None:
                return result

        return str(value).strip()

    def _group_translations_by_file(
        self, translations: dict[str, Any], empty_keys: list[dict]
    ) -> dict[str, dict[str, Any]]:
        """Group translations by file path."""
        translations_by_file: dict[str, dict[str, Any]] = {}

        for key_info in empty_keys:
            file_path_str = str(Path(key_info["file_path"]).resolve())
            # Include msgctxt in key if it exists to match key structure
            msgctxt = key_info.get("msgctxt")
            if msgctxt:
                translation_key = f"{file_path_str}:{msgctxt}:{key_info['key']}"
            else:
                translation_key = f"{file_path_str}:{key_info['key']}"

            if translation_key in translations:
                trans_value = translations[translation_key]
                if trans_value is None:
                    continue  # Skip missing translations
                file_type = key_info.get("file_type", "po")
                is_plural = key_info.get("is_plural", False)

                if file_type == "json" and isinstance(trans_value, dict):
                    if "singular" in trans_value and "plural" in trans_value:
                        trans_value = self._process_llm_response_value(
                            trans_value, key_info, file_type, is_plural=is_plural
                        )
                    else:
                        trans_value = trans_value.get("singular", str(trans_value))

                # For PO files, include msgctxt in key for apply_po_translations
                if key_info["file_type"] == "po" and msgctxt:
                    # Store with msgctxt prefix for proper matching
                    po_key = f"{msgctxt}:{key_info['key']}"
                else:
                    po_key = key_info["key"]

                translations_by_file.setdefault(file_path_str, {})[po_key] = trans_value

        return translations_by_file

    def _apply_file_translations(
        self,
        file_path: Path,
        file_translations: dict[str, Any],
        empty_keys: list[dict],
        stdout,
    ) -> tuple[int, str]:
        """Apply translations to a single file. Returns (count, app)."""
        if not file_path.exists():
            stdout.write(self.style.WARNING(f"   WARNING: File not found: {file_path}"))
            return 0, "unknown"

        # Normalize paths for comparison
        normalized_file_path = str(file_path.resolve())
        key_info = next(
            k
            for k in empty_keys
            if str(Path(k["file_path"]).resolve()) == normalized_file_path
        )
        app = key_info.get("app", "unknown")

        logger.debug(
            "Applying %d translation(s) to %s (type: %s, app: %s)",
            len(file_translations),
            file_path.name,
            key_info["file_type"],
            app,
        )
        if key_info["file_type"] == "json":
            count = apply_json_translations(file_path, file_translations)
        elif key_info["file_type"] == "po":
            count = apply_po_translations(file_path, file_translations)
        else:
            logger.warning(
                "Unknown file type '%s' for file: %s", key_info["file_type"], file_path
            )
            return 0, app

        if count > 0:
            logger.info(
                "Applied %d translation(s) to %s (app: %s)", count, file_path.name, app
            )

        return count, app

    def _apply_translations(
        self,
        translations: dict[str, Any],
        empty_keys: list[dict],
        stdout,
    ) -> tuple[int, dict[str, Any]]:
        """Apply translations to files."""
        translations_by_file = self._group_translations_by_file(
            translations, empty_keys
        )

        if not translations_by_file:
            stdout.write(self.style.WARNING("   WARNING: No translations to apply"))
            return 0, {"by_app": {}, "details": []}

        applied = 0
        applied_by_app: dict[str, int] = {}
        applied_details: list[dict[str, Any]] = []

        for file_path_str, file_translations in translations_by_file.items():
            full_path = Path(file_path_str)
            count, app = self._apply_file_translations(
                full_path, file_translations, empty_keys, stdout
            )

            applied += count
            if count > 0:
                applied_by_app[app] = applied_by_app.get(app, 0) + count
                applied_details.append(
                    {"app": app, "file": full_path.name, "count": count}
                )
                stdout.write(
                    f"   Applied {count} translations to {app} ({full_path.name})"
                )

        if applied_by_app:
            app_summary = ", ".join(
                f"{app}: {count}" for app, count in applied_by_app.items()
            )
            stdout.write(f"   Summary by app: {app_summary}")

        return applied, {"by_app": applied_by_app, "details": applied_details}

    def _cleanup_failed_branch(self, repo: GitRepository, branch_name: str) -> None:
        """Clean up branch if PR creation fails."""
        try:
            repo.switch_to_main()
            # Only try to delete if branch exists locally
            if branch_name in [ref.name for ref in repo.repo.heads]:
                with suppress(git.exc.GitCommandError):
                    repo.repo.git.branch("-D", branch_name)
                    self.stdout.write(
                        self.style.WARNING(
                            f"   Cleaned up failed branch: {branch_name}"
                        )
                    )
        except (git.exc.GitCommandError, AttributeError) as e:
            self.stdout.write(
                self.style.WARNING(f"   Could not clean up branch {branch_name}: {e!s}")
            )

    def _commit_changes(
        self, repo: GitRepository, branch_name: str, lang_code: str
    ) -> bool:
        """Commit changes to git repository. Returns True if committed."""
        # Check if branch already exists
        if repo.branch_exists(branch_name):
            self.stdout.write(
                self.style.WARNING(
                    f"   Branch '{branch_name}' already exists. "
                    f"Switching to it and continuing..."
                )
            )
            try:
                repo.repo.git.checkout(branch_name)
            except git.exc.GitCommandError:
                # If local branch doesn't exist but remote does, create tracking branch
                repo.repo.git.checkout("-b", branch_name, f"origin/{branch_name}")
        else:
            repo.configure_user()
            repo.create_branch(branch_name)
        repo.stage_all()

        if not repo.has_changes():
            self.stdout.write(
                self.style.WARNING(
                    "   No changes to commit. Skipping commit and PR creation."
                )
            )
            repo.switch_to_main()
            with suppress(git.exc.GitCommandError):
                repo.repo.git.branch("-D", branch_name)
            return False

        safe_lang_code = sanitize_for_git(lang_code)
        commit_message = (
            f"feat: Add {safe_lang_code} translations via LLM\n\n"
            f"Automated translation of empty keys for {safe_lang_code} language."
        )

        repo.commit(commit_message)

        github_token = getattr(
            settings, "TRANSLATIONS_GITHUB_TOKEN", None
        ) or os.environ.get("TRANSLATIONS_GITHUB_TOKEN")
        repo.push_branch(branch_name, github_token)
        self.stdout.write("   Pushed branch to remote")

        return True

    def _create_pull_request(
        self,
        repo_path: str,
        branch_name: str,
        pr_data: PullRequestData,
        repo_url: str,
    ) -> str:
        """Create pull request using GitHub CLI or API."""
        iso_code = pr_data["iso_code"]
        provider = pr_data["provider"]
        model = pr_data["model"]
        provider_display = provider.replace("_", " ").title()
        pr_title = (
            f"feat: Add {iso_code} translations via LLM using "
            f"{provider_display} provider and model {model}"
        )
        try:
            # Using GitHub CLI (gh) - trusted system command
            gh_path = shutil.which("gh")
            if gh_path:
                result = subprocess.run(  # noqa: S603
                    [
                        gh_path,
                        "pr",
                        "create",
                        "--title",
                        pr_title,
                        "--body",
                        self._generate_pr_body(pr_data),
                    ],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        # Fall back to API if gh CLI is not available or fails
        return self._create_pr_via_api(
            repo_path,
            branch_name,
            pr_data,
            repo_url,
            pr_title=pr_title,
        )

    def _generate_error_section(
        self, errors: int, errors_by_app: dict[str, int] | None = None
    ) -> str:
        """Generate error warning section for PR body if there are errors.

        Args:
            errors: Number of translation errors.
            errors_by_app: Dictionary mapping app/MFE names to error counts.

        Returns:
            Error section markdown string, or empty string if no errors.
        """
        if errors == 0:
            return ""

        error_details = ""
        if errors_by_app:
            error_lines = [
                f"- **{app}**: {count} key(s) failed"
                for app, count in sorted(
                    errors_by_app.items(), key=lambda x: x[1], reverse=True
                )
            ]
            error_details = (
                "\n**Errors by app/MFE:**\n\n" + "\n".join(error_lines) + "\n"
            )

        error_template = f"""
            ### Translation Errors

            **{errors} translation key(s) failed to translate** due to API errors, rate
            limits, or parsing issues.
            {error_details}
            **Impact:**
            - These keys remain untranslated in the target language files
            - They will need to be translated manually or re-run the command
            - The translation process continued and completed successfully
              for the remaining keys

            **Recommendation:**
            - Review the command output logs for specific error details
            - Consider re-running the command to retry failed batches
            - Check API key permissions and rate limits if errors persist

            """
        return textwrap.dedent(error_template)

    def _generate_translation_summary(
        self, glossary_matches: int, llm_translations: int, errors: int
    ) -> str:
        """Generate translation statistics summary line.

        Args:
            glossary_matches: Number of glossary matches.
            llm_translations: Number of LLM translations.
            errors: Number of translation errors.

        Returns:
            Summary string.
        """
        if glossary_matches > 0:
            return (
                f"Summary - Glossary matches: {glossary_matches}, "
                f"LLM translations: {llm_translations}, Errors: {errors}"
            )
        return f"Summary - LLM translations: {llm_translations}, Errors: {errors}"

    def _generate_pr_body(self, pr_data: PullRequestData) -> str:
        """Generate PR description."""
        lang_code = pr_data["lang_code"]
        iso_code = pr_data["iso_code"]
        sync_stats = pr_data["sync_stats"]
        applied_count = pr_data["applied_count"]
        translation_stats = pr_data["translation_stats"]
        applied_by_app = pr_data["applied_by_app"]
        provider = pr_data["provider"]
        model = pr_data["model"]

        glossary_matches = translation_stats.get("glossary_matches", 0)
        llm_translations = translation_stats.get("llm_translations", 0)
        errors = translation_stats.get("errors", 0)
        errors_by_app: dict[str, int] = cast(
            "dict[str, int]", translation_stats.get("errors_by_app", {})
        )

        translation_summary = self._generate_translation_summary(
            glossary_matches, llm_translations, errors
        )
        error_section = self._generate_error_section(errors, errors_by_app)

        applied_details = applied_by_app.get("details", [])
        breakdown_lines = [
            f"   Applied {detail['count']} translations to "
            f"{detail['app']} ({detail['file']})"
            for detail in applied_details
        ]

        # Build changes section with conditional error line
        changes_lines = [
            f"- **Language**: {lang_code} ({iso_code})",
            f"- **Keys synced**: {sync_stats['frontend']['added']} frontend keys, "
            f"{sync_stats['backend']['added']} backend entries",
            f"- **Translations applied**: {applied_count} keys translated",
            f"- **Typos fixed**: {sync_stats['frontend']['fixed']}",
        ]
        if errors > 0:
            changes_lines.append(
                f"- **Translation errors**: {errors} keys failed to translate"
            )

        # Build statistics section with conditional error line
        statistics_lines = [
            translation_summary,
            f"   Translated {applied_count} keys",
        ]
        if errors > 0:
            statistics_lines.append(f"   Failed: {errors} keys")

        # Build next steps section with conditional error line
        next_steps_lines = [
            "- Review translations for accuracy",
        ]
        if errors > 0:
            next_steps_lines.append(
                "- Address failed translations (see error section above)"
            )
        next_steps_lines.extend(
            [
                "- Test in staging environment",
                "- Merge when ready",
            ]
        )

        provider_display = provider.replace("_", " ").title()
        pr_template = (
            f"""## Summary

            This PR adds {iso_code} translations via LLM automation using {
                provider_display
            } provider and model {model}.
            {error_section}
            ### Changes

            {chr(10).join(changes_lines)}

            ### Translation Statistics

            {chr(10).join(statistics_lines)}

            ### Applied Translations

            {
                chr(10).join(breakdown_lines)
                if breakdown_lines
                else "   No translations applied"
            }

            ### Files Modified

            - Frontend apps: {sync_stats["frontend"]["created"]} created, """
            f"""{sync_stats["frontend"]["synced"]} synced
            - Backend: PO files updated

            ### Next Steps

            {chr(10).join(next_steps_lines)}

            ---
            *This PR was automatically generated by the sync_and_translate_language """
            f"""management command.*
            """
        )
        return textwrap.dedent(pr_template)

    def _create_pr_via_api(
        self,
        repo_path: str,
        branch_name: str,
        pr_data: PullRequestData,
        repo_url: str,
        pr_title: str,
    ) -> str:
        """Create PR using GitHub API."""
        client = GitHubAPIClient()
        owner, repo = GitHubAPIClient.parse_repo_url(repo_url)

        git_repo = GitRepository(repo_path)
        main_branch = git_repo._get_main_branch_name()  # noqa: SLF001

        return client.create_pull_request(
            owner=owner,
            repo=repo,
            branch_name=branch_name,
            title=pr_title,
            body=self._generate_pr_body(pr_data),
            base=main_branch,
            stdout=self.stdout,
        )
