"""
Django management command to sync translation keys, translate using LLM, and create PRs.

Usage:
    python manage.py sync_and_translate_language el
    python manage.py sync_and_translate_language fr --model gpt-4
"""

import json
import os
import re
import subprocess
import time
import urllib.parse
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

import git
import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from litellm import completion

from ol_openedx_course_translations.utils.command_utils import (
    create_branch_name,
    get_config_value,
    is_retryable_error,
    sanitize_for_git,
    validate_branch_name,
    validate_language_code,
)
from ol_openedx_course_translations.utils.constants import LANGUAGE_MAPPING, MAX_RETRIES
from ol_openedx_course_translations.utils.translation_sync import (
    apply_json_translations,
    apply_po_translations,
    extract_empty_keys,
    load_glossary,
    match_glossary_term,
    sync_all_translations,
)

# ============================================================================
# Git Repository Helper Class
# ============================================================================


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
        Determine the main branch name (main or master).
        Checks local branches first, then remote branches.
        Fetches from remote if needed to check remote branches.
        """
        # First check if 'main' exists locally
        if "main" in [ref.name for ref in self.repo.heads]:
            return "main"
        # Then check if 'master' exists locally
        if "master" in [ref.name for ref in self.repo.heads]:
            return "master"

        # If not found locally, fetch from remote and check remote branches
        try:
            self.repo.remotes.origin.fetch()
        except git.exc.GitCommandError:
            # If fetch fails, we'll try to check existing remote refs anyway
            pass

        # Check remote branches
        if "origin/main" in [ref.name for ref in self.repo.remotes.origin.refs]:
            return "main"
        if "origin/master" in [ref.name for ref in self.repo.remotes.origin.refs]:
            return "master"

        raise CommandError(
            "Neither 'main' nor 'master' branch found locally or on remote"
        )

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

            # Determine which branch name to use (main or master)
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
        """Fetch and pull latest changes from origin/main or origin/master."""
        try:
            self.repo.remotes.origin.fetch()
            main_branch = self._get_main_branch_name()
            self.repo.git.pull("origin", main_branch)
        except git.exc.GitCommandError as e:
            self._handle_git_error("updating repository", e)

    def configure_user(
        self,
        email: str = "translations@mitodl.org",
        name: str = "MIT Open Learning Translations Bot",
    ) -> None:
        """Configure git user for this repository."""
        try:
            with self.repo.config_writer() as config:
                if not config.get_value("user", "email", default=None):
                    config.set_value("user", "email", email)
                if not config.get_value("user", "name", default=None):
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
            try:
                self.repo.remotes.origin.fetch()
            except git.exc.GitCommandError:
                # If fetch fails, try to check existing remote refs anyway
                pass
            remote_branch = f"origin/{branch_name}"
            if remote_branch in [ref.name for ref in self.repo.remotes.origin.refs]:
                return True
            return False
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
            except Exception:
                pass  # Best effort cleanup

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


# ============================================================================
# GitHub API Client
# ============================================================================


class GitHubAPIClient:
    """Helper class for GitHub API operations."""

    def __init__(self, token: str | None = None):
        """Initialize with optional token."""
        self.token = (
            token
            or getattr(settings, "GITHUB_TOKEN", None)
            or os.environ.get("GITHUB_TOKEN")
        )
        if not self.token:
            msg = "GITHUB_TOKEN not set in settings or environment"
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
        return match.groups()

    def _handle_rate_limit(
        self, response: requests.Response, attempt: int, max_retries: int, stdout
    ) -> bool:
        """Handle rate limit response. Returns True if should retry."""
        if response.status_code == 429:
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
        """Extract safe error message from response."""
        try:
            error_data = response.json()
            return error_data.get("message", f"HTTP {response.status_code}")
        except Exception:
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

        if response.status_code == 404:
            msg = (
                f"Branch '{branch_name}' not found on remote. "
                f"Ensure the branch was pushed successfully."
            )
            raise CommandError(msg)
        elif response.status_code != 200:
            error_msg = self._extract_error_message(response)
            msg = f"Failed to verify branch: {error_msg}"
            raise CommandError(msg)

    def create_pull_request(
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

                if response.status_code == 201:
                    return response.json()["html_url"]

                if self._handle_rate_limit(
                    response, attempt, max_retries, stdout or self
                ):
                    continue

                if response.status_code == 422:
                    error_msg = self._extract_error_message(response)
                    safe_error = error_msg[:200] if len(error_msg) > 200 else error_msg
                    msg = (
                        f"GitHub API validation error: {safe_error}\n"
                        f"This usually means the branch doesn't exist on remote "
                        f"or there's already a PR for this branch."
                    )
                    raise CommandError(msg)

                error_msg = self._extract_error_message(response)
                safe_error = error_msg[:200] if len(error_msg) > 200 else error_msg
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
                            f"   Connection error (attempt {attempt + 1}/{max_retries}): "
                            f"{e!s}"
                        )
                        stdout.write(error_msg)
                        stdout.write(f"   Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    continue
                else:
                    if is_connection_error:
                        raise CommandError(
                            f"Failed to connect to GitHub API after {max_retries} attempts: {e!s}\n"
                            f"Please check your network connection and try again later."
                        )
                    raise CommandError(f"GitHub API error: {e!s}")


# ============================================================================
# Main Command Class
# ============================================================================


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
            help="Path to mitxonline-translations repository. "
            "Can also be set via REPO_PATH setting or environment variable.",
        )
        parser.add_argument(
            "--model",
            type=str,
            default=getattr(
                settings, "TRANSLATIONS_DEFAULT_MODEL", "mistral/mistral-large-latest"
            ),
            help="Model name (e.g., gpt-4, claude-3-opus-20240229, mistral/mistral-large-latest). "
            "LiteLLM automatically detects provider from model name. "
            "Mistral models: mistral/mistral-small-latest, mistral/mistral-medium-latest, ",
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
            "Looks for {plugin_dir}/glossaries/machine_learning/{lang_code}.txt",
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
                "Can also be set via REPO_URL setting or environment variable."
            ),
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Handle the command execution."""
        lang_code = options["lang"]
        iso_code = options.get("iso_code") or lang_code

        # Validate inputs
        validate_language_code(lang_code)
        validate_language_code(iso_code, "ISO code")

        repo_path = get_config_value(
            "repo_path",
            options,
            os.path.join(os.path.expanduser("~"), ".mitxonline-translations"),
        )
        repo_url = get_config_value(
            "repo_url",
            options,
            "https://github.com/mitodl/mitxonline-translations.git",
        )

        # Validate repository path is not empty
        if not repo_path or not repo_path.strip():
            raise CommandError(
                "Repository path is not set. Please specify --repo-path, "
                "set TRANSLATIONS_REPO_PATH in Django settings, or set "
                "TRANSLATIONS_REPO_PATH environment variable."
            )

        self.stdout.write(self.style.SUCCESS(f"Processing language: {lang_code}"))
        self.stdout.write(f"   ISO code: {iso_code}")
        self.stdout.write(f"   Repository: {repo_path}")

        # Ensure repository is ready
        repo = self._ensure_repo(repo_path, repo_url)

        # Sync translation keys
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

        # Load glossary if enabled
        glossary = self._load_glossary(options, lang_code)

        # Translate keys
        self.stdout.write(f"\nTranslating using {options['model']}...")
        translations, translation_stats = self._translate_keys(
            empty_keys,
            lang_code,
            options["model"],
            glossary,
            options.get("batch_size", 200),
            MAX_RETRIES,
        )
        self.stdout.write(f"   Translated {len(translations)} keys")

        # Apply translations
        self.stdout.write("\nApplying translations...")
        applied_count, applied_by_app = self._apply_translations(
            base_dir, translations, empty_keys, self.stdout
        )
        self.stdout.write(f"   Applied {applied_count} translations")

        if options.get("dry_run"):
            self.stdout.write(self.style.WARNING("\nDry run - no changes committed"))
            return

        # Commit and create PR
        branch_name = create_branch_name(lang_code)
        self.stdout.write(f"\nCommitting changes to branch: {branch_name}")

        if not self._commit_changes(repo, branch_name, lang_code):
            return

        self.stdout.write("\nCreating pull request...")
        try:
            pr_url = self._create_pull_request(
                repo_path,
                branch_name,
                lang_code,
                iso_code,
                sync_stats,
                applied_count,
                translation_stats,
                applied_by_app,
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
            self.stdout.write(f"   Repository found at {repo_path}")
            repo = GitRepository(repo_path)

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
            raise CommandError(
                f"Path {repo_path} exists but is not a git repository. "
                f"Please remove it or specify a different path."
            )
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
        available_apps = set(key.get("app", "unknown") for key in empty_keys)
        filtered = [key for key in empty_keys if key.get("app") in mfe_set]

        if not filtered:
            self.stdout.write(
                self.style.WARNING(
                    f"\nWARNING: No empty keys found for specified MFE(s): {', '.join(mfe_filter)}\n"
                    f"   Available apps: {', '.join(sorted(available_apps))}"
                )
            )
            return []

        self.stdout.write(
            f"   Filtered to {len(filtered)} keys from {len(mfe_set)} MFE(s): {', '.join(mfe_filter)} "
            f"(was {original_count} total)"
        )
        return filtered

    def _load_glossary(self, options: dict, lang_code: str) -> dict[str, Any]:
        """Load glossary if enabled."""
        if not options.get("glossary", False):
            return {}

        import ol_openedx_course_translations.utils.translation_sync as utils_module

        utils_file = Path(utils_module.__file__)
        glossary_path = (
            utils_file.parent.parent
            / "glossaries"
            / "machine_learning"
            / f"{lang_code}.txt"
        )

        if glossary_path.exists():
            self.stdout.write(f"\nLoading glossary from {glossary_path}...")
            glossary = load_glossary(glossary_path, lang_code)
            self.stdout.write(f"   Loaded {len(glossary)} glossary terms")
            return glossary

        self.stdout.write(
            self.style.WARNING(
                f"\nWARNING: Glossary file not found: {glossary_path}\n"
                f"   Continuing without glossary."
            )
        )
        return {}

    def _translate_keys(
        self,
        empty_keys: list[dict],
        lang_code: str,
        model: str,
        glossary: dict[str, Any] | None,
        batch_size: int = 200,
        max_retries: int = MAX_RETRIES,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        """Translate empty keys using LLM with batch processing."""
        translations = {}
        glossary_matches = 0
        llm_translations = 0
        llm_errors = 0
        errors_by_app: dict[str, int] = {}  # Track errors by app/MFE

        # First pass: check glossary matches
        keys_needing_llm = []
        for key_info in empty_keys:
            # Normalize file path for consistent comparison
            file_path_str = str(Path(key_info["file_path"]).resolve())
            translation_key = f"{file_path_str}:{key_info['key']}"

            if glossary:
                match_result = self._check_glossary_match(key_info, glossary)
                if match_result:
                    translations[translation_key] = match_result
                    glossary_matches += 1
                    continue

            keys_needing_llm.append(key_info)

        if not keys_needing_llm:
            return translations, {
                "glossary_matches": glossary_matches,
                "llm_translations": 0,
                "errors": 0,
                "errors_by_app": {},
            }

        # Translate remaining keys with LLM
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
            # Track which apps/MFEs are in this batch
            batch_apps = set(key_info.get("app", "unknown") for key_info in batch)

            # Retry loop for this batch
            for attempt in range(max_retries + 1):  # +1 for initial attempt
                try:
                    batch_translations = self._call_llm_batch(
                        batch, lang_code, model, glossary
                    )
                    batch_successes = 0
                    batch_partial_errors = 0
                    batch_errors_by_app: dict[str, int] = {}

                    for i, key_info in enumerate(batch):
                        # Normalize file path for consistent comparison
                        file_path_str = str(Path(key_info["file_path"]).resolve())
                        translation_key = f"{file_path_str}:{key_info['key']}"
                        app = key_info.get("app", "unknown")
                        if i < len(batch_translations) and batch_translations[i]:
                            translations[translation_key] = batch_translations[i]
                            llm_translations += 1
                            batch_successes += 1
                        else:
                            llm_errors += 1
                            batch_partial_errors += 1
                            batch_errors_by_app[app] = (
                                batch_errors_by_app.get(app, 0) + 1
                            )
                            errors_by_app[app] = errors_by_app.get(app, 0) + 1

                    completed = min(batch_idx * batch_size, total_keys)
                    progress_pct = min((completed / total_keys) * 100, 100)
                    # Calculate remaining keys (total_keys is only for LLM translations, not glossary)
                    remaining_keys = total_keys - llm_translations

                    if batch_partial_errors > 0:
                        retry_msg = (
                            f" (after {attempt + 1} attempt(s))" if attempt > 0 else ""
                        )
                        apps_str = ", ".join(sorted(batch_apps))
                        errors_by_app_str = ", ".join(
                            f"{app}: {count}"
                            for app, count in sorted(batch_errors_by_app.items())
                        )
                        self.stdout.write(
                            f"   Batch {batch_idx}/{num_batches} completed with partial success "
                            f"({batch_successes} succeeded, {batch_partial_errors} failed){retry_msg} "
                            f"({completed}/{total_keys} keys, {progress_pct:.1f}% complete, {remaining_keys} remaining)\n"
                            f"         Affected apps: {apps_str}\n"
                            f"         Errors by app: {errors_by_app_str}"
                        )
                    else:
                        retry_msg = (
                            f" (after {attempt + 1} attempt(s))" if attempt > 0 else ""
                        )
                        self.stdout.write(
                            f"   Batch {batch_idx}/{num_batches} completed{retry_msg} "
                            f"({completed}/{total_keys} keys, {progress_pct:.1f}% complete, {remaining_keys} remaining)"
                        )

                    batch_succeeded = True
                    break  # Success - exit retry loop

                except Exception as e:
                    apps_str = ", ".join(sorted(batch_apps))
                    # Check if error is retryable
                    if not is_retryable_error(e):
                        # Non-retryable error - fail immediately
                        self.stdout.write(
                            self.style.ERROR(
                                f"   ERROR: Batch {batch_idx}/{num_batches} failed with non-retryable error: {e!s}\n"
                                f"         Affected apps: {apps_str}"
                            )
                        )
                        break

                    # Retryable error - check if we have retries left
                    if attempt < max_retries:
                        # Exponential backoff: 2^attempt seconds (1s, 2s, 4s, 8s...)
                        wait_time = 2**attempt
                        self.stdout.write(
                            self.style.WARNING(
                                f"   WARNING: Batch {batch_idx}/{num_batches} failed (attempt {attempt + 1}/{max_retries + 1}): {e!s}\n"
                                f"         Affected apps: {apps_str}\n"
                                f"         Retrying in {wait_time} second(s)..."
                            )
                        )
                        time.sleep(wait_time)
                    else:
                        # Out of retries
                        self.stdout.write(
                            self.style.ERROR(
                                f"   ERROR: Batch {batch_idx}/{num_batches} failed after {max_retries + 1} attempts: {e!s}\n"
                                f"         Affected apps: {apps_str}"
                            )
                        )

            # If batch failed after all retries, mark all keys as errors
            if not batch_succeeded:
                batch_errors = len(batch)
                llm_errors += batch_errors
                # Track errors by app for this failed batch
                for key_info in batch:
                    app = key_info.get("app", "unknown")
                    errors_by_app[app] = errors_by_app.get(app, 0) + 1
                apps_str = ", ".join(sorted(batch_apps))
                self.stdout.write(
                    self.style.ERROR(
                        f"         Marked {batch_errors} keys as errors, continuing with next batch...\n"
                        f"         Affected apps: {apps_str}"
                    )
                )
                # Continue to next batch - don't break the loop

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
            singular_match = match_glossary_term(
                key_info["english"], glossary, exact_match=True
            )
            plural_match = match_glossary_term(msgid_plural, glossary, exact_match=True)

            if singular_match and plural_match:
                if isinstance(singular_match, dict) and "singular" in singular_match:
                    return singular_match
                elif isinstance(plural_match, dict) and "singular" in plural_match:
                    return plural_match
                else:
                    return {
                        "singular": str(singular_match),
                        "plural": str(plural_match),
                    }
            elif singular_match:
                key_info["_glossary_singular"] = (
                    str(singular_match)
                    if isinstance(singular_match, str)
                    else singular_match.get("singular", "")
                )
                return None  # Need LLM for plural
        else:
            match = match_glossary_term(key_info["english"], glossary, exact_match=True)
            if match:
                if isinstance(match, dict):
                    return match.get("translation", match.get("singular", ""))
                return match

        return None

    def _format_glossary_for_prompt(self, glossary: dict[str, Any] | None) -> str:
        """Format glossary as a prompt section for LLM translation requests.

        Args:
            glossary: Dictionary mapping English terms to translations, or None/empty dict.

        Returns:
            Empty string if glossary is None or empty, otherwise returns a formatted
            string with glossary terms and instructions for consistent translation.
        """
        if not glossary:
            return ""

        # Format glossary as JSON for the prompt
        # Handle potential serialization errors gracefully
        try:
            glossary_json = json.dumps(glossary, indent=2, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            # If glossary contains non-serializable values, log warning and skip
            self.stdout.write(
                self.style.WARNING(
                    f"   WARNING: Could not serialize glossary for prompt: {e!s}. "
                    f"Continuing without glossary in LLM prompt."
                )
            )
            return ""
        return f"""

IMPORTANT - Use these glossary terms when translating. If any English terms from the glossary appear in the texts to translate, use the corresponding translation from the glossary:

{glossary_json}

When translating sentences, ensure that glossary terms are translated consistently according to the glossary above, even if they appear within longer sentences. For example, if the glossary specifies "certificate" -> "Πιστοποιητικό", then translate "certificate" as "Πιστοποιητικό" even when it appears in longer sentences like "The course completion certificate is available".
"""

    def _call_llm_batch(
        self,
        key_batch: list[dict],
        lang_code: str,
        model: str,
        glossary: dict[str, Any] | None = None,
        timeout: int = 120,
    ) -> list[str | dict]:
        """Call LLM API to translate multiple texts in a single request.

        Args:
            key_batch: List of key information dictionaries to translate
            lang_code: Target language code
            model: LLM model name
            glossary: Optional glossary dictionary
            timeout: Request timeout in seconds (default: 120)
        """
        api_key = self._get_llm_api_key(model)

        texts_dict = {}
        plural_entries = {}
        for i, key_info in enumerate(key_batch, 1):
            key_str = str(i)
            if key_info.get("is_plural") and key_info.get("msgid_plural"):
                texts_dict[key_str] = {
                    "singular": key_info["english"],
                    "plural": key_info.get("msgid_plural", ""),
                }
                plural_entries[key_str] = True
            else:
                texts_dict[key_str] = key_info["english"]

        texts_block = json.dumps(texts_dict, indent=2, ensure_ascii=False)
        plural_count = len(plural_entries)

        lang_name = LANGUAGE_MAPPING.get(lang_code, lang_code)

        # Build glossary section if glossary is provided
        glossary_section = self._format_glossary_for_prompt(glossary)

        prompt = f"""Translate the following {len(key_batch)} text(s) to {lang_name} (language code: {lang_code}).
Context: These are from an educational platform.
Preserve any placeholders like {{variable}}, {{0}}, %s, etc.
Preserve HTML tags and formatting.
{glossary_section}
{("IMPORTANT: " + str(plural_count) + ' entry/entries have plural forms. For these, return BOTH singular and plural translations as an object with "singular" and "plural" keys.') if plural_count > 0 else ""}

Return a JSON object where each key is the number (1, 2, 3, etc.).
- For singular entries: value is the translation string.
- For plural entries: value is an object with "singular" and "plural" keys, each containing the translation.

Input texts (numbered):
{texts_block}

Return ONLY valid JSON in this format:
{{
  "1": "translation of first text",
  "2": {{"singular": "singular translation", "plural": "plural translation"}},
  "3": "translation of third text",
  ...
}}"""

        try:
            completion_kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "timeout": timeout,
            }
            if api_key:
                completion_kwargs["api_key"] = api_key

            response = completion(**completion_kwargs)
            response_text = response.choices[0].message.content.strip()

            translations = self._parse_json_response(response_text, key_batch)
            if translations:
                return translations

            return self._parse_order_based_response(response_text, key_batch)

        except TimeoutError:
            raise CommandError(
                f"LLM batch API call timed out after {timeout} seconds.\n"
                f"Model: {model}\n"
                f"Batch size: {len(key_batch)}\n"
                f"Try reducing --batch-size or check your network connection."
            )
        except Exception as e:
            raise CommandError(
                f"LLM batch API call failed: {e!s}\n"
                f"Model: {model}\n"
                f"Batch size: {len(key_batch)}\n"
                f"Make sure the appropriate API key is set (e.g., OPENAI_API_KEY, ANTHROPIC_API_KEY, MISTRAL_API_KEY)"
            )

    def _parse_json_response(
        self, response_text: str, key_batch: list[dict]
    ) -> list[str | dict] | None:
        """Parse JSON response from LLM."""
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

        try:
            data = json.loads(json_text)
            translations = []
            for i in range(len(key_batch)):
                key = str(i + 1)
                if key in data:
                    value = data[key]
                    if (
                        isinstance(value, dict)
                        and "singular" in value
                        and "plural" in value
                    ):
                        translations.append(
                            {
                                "singular": str(value["singular"]).strip(),
                                "plural": str(value["plural"]).strip(),
                            }
                        )
                    else:
                        translations.append(str(value).strip())
                else:
                    translations.append("")
            return translations
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def _parse_order_based_response(
        self, response_text: str, key_batch: list[dict]
    ) -> list[str]:
        """Fallback: Parse response assuming translations are in order."""
        lines = [line.strip() for line in response_text.split("\n") if line.strip()]
        cleaned_lines = [
            line.lstrip("0123456789.-) ").strip()
            for line in lines
            if line.lstrip("0123456789.-) ").strip()
        ]
        if len(cleaned_lines) < len(key_batch):
            cleaned_lines.extend([""] * (len(key_batch) - len(cleaned_lines)))
        return cleaned_lines[: len(key_batch)]

    def _get_llm_api_key(self, model: str) -> str | None:
        """Get API key for the model from environment or settings."""
        model_lower = model.lower()
        key_name = (
            "ANTHROPIC_API_KEY"
            if "claude" in model_lower or "anthropic" in model_lower
            else "GOOGLE_API_KEY"
            if "gemini" in model_lower or "google" in model_lower
            else "MISTRAL_API_KEY"
            if "mistral" in model_lower
            else None
            if "ollama" in model_lower
            else "OPENAI_API_KEY"
        )
        if not key_name:
            return None
        try:
            if hasattr(settings, key_name):
                return getattr(settings, key_name)
        except Exception:
            pass
        return os.environ.get(key_name)

    def _apply_translations(
        self,
        base_dir: Path,
        translations: dict[str, Any],
        empty_keys: list[dict],
        stdout,
    ) -> tuple[int, dict[str, Any]]:
        """Apply translations to files."""
        applied = 0
        translations_by_file = {}

        for key_info in empty_keys:
            # Normalize file path for consistent comparison
            file_path_str = str(Path(key_info["file_path"]).resolve())
            translation_key = f"{file_path_str}:{key_info['key']}"
            if translation_key in translations:
                trans_value = translations[translation_key]

                if key_info["file_type"] == "json" and isinstance(trans_value, dict):
                    trans_value = trans_value.get("singular", str(trans_value))

                translations_by_file.setdefault(file_path_str, {})[key_info["key"]] = (
                    trans_value
                )

        if not translations_by_file:
            stdout.write(self.style.WARNING("   WARNING: No translations to apply"))
            return 0, {"by_app": {}, "details": []}

        applied_by_app: dict[str, int] = {}
        applied_details: list[dict[str, Any]] = []

        for file_path, file_translations in translations_by_file.items():
            full_path = Path(file_path)
            if not full_path.exists():
                stdout.write(
                    self.style.WARNING(f"   WARNING: File not found: {full_path}")
                )
                continue

            # Normalize paths for comparison
            normalized_file_path = str(full_path.resolve())
            key_info = next(
                k
                for k in empty_keys
                if str(Path(k["file_path"]).resolve()) == normalized_file_path
            )
            app = key_info.get("app", "unknown")

            if key_info["file_type"] == "json":
                count = apply_json_translations(full_path, file_translations)
            elif key_info["file_type"] == "po":
                count = apply_po_translations(full_path, file_translations)
            else:
                continue

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
            if repo.branch_exists(branch_name):
                repo.repo.git.branch("-D", branch_name)
                self.stdout.write(
                    self.style.WARNING(f"   Cleaned up failed branch: {branch_name}")
                )
        except Exception as e:
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
            try:
                repo.repo.git.branch("-D", branch_name)
            except Exception:
                pass
            return False

        safe_lang_code = sanitize_for_git(lang_code)
        commit_message = (
            f"feat: Add {safe_lang_code} translations via LLM\n\n"
            f"Automated translation of empty keys for {safe_lang_code} language."
        )

        repo.commit(commit_message)

        github_token = getattr(settings, "GITHUB_TOKEN", None) or os.environ.get(
            "GITHUB_TOKEN"
        )
        repo.push_branch(branch_name, github_token)
        self.stdout.write("   Pushed branch to remote")

        return True

    def _create_pull_request(
        self,
        repo_path: str,
        branch_name: str,
        lang_code: str,
        iso_code: str,
        sync_stats: dict,
        applied_count: int,
        translation_stats: dict[str, int],
        applied_by_app: dict[str, Any],
        repo_url: str,
    ) -> str:
        """Create pull request using GitHub CLI or API."""
        try:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "create",
                    "--title",
                    f"feat: Add {lang_code} translations via LLM",
                    "--body",
                    self._generate_pr_body(
                        lang_code,
                        iso_code,
                        sync_stats,
                        applied_count,
                        translation_stats,
                        applied_by_app,
                    ),
                ],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return self._create_pr_via_api(
                repo_path,
                branch_name,
                lang_code,
                iso_code,
                sync_stats,
                applied_count,
                translation_stats,
                applied_by_app,
                repo_url,
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

        return f"""
### Translation Errors

**{errors} translation key(s) failed to translate** due to API errors, rate limits, or parsing issues.
{error_details}
**Impact:**
- These keys remain untranslated in the target language files
- They will need to be translated manually or re-run the command
- The translation process continued and completed successfully for the remaining keys

**Recommendation:**
- Review the command output logs for specific error details
- Consider re-running the command to retry failed batches
- Check API key permissions and rate limits if errors persist

"""

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

    def _generate_pr_body(
        self,
        lang_code: str,
        iso_code: str,
        sync_stats: dict,
        applied_count: int,
        translation_stats: dict[str, int],
        applied_by_app: dict[str, Any],
    ) -> str:
        """Generate PR description."""
        glossary_matches = translation_stats.get("glossary_matches", 0)
        llm_translations = translation_stats.get("llm_translations", 0)
        errors = translation_stats.get("errors", 0)
        errors_by_app = translation_stats.get("errors_by_app", {})

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

        return f"""## Summary

This PR adds {lang_code} translations via LLM automation.
{error_section}
### Changes

{chr(10).join(changes_lines)}

### Translation Statistics

{chr(10).join(statistics_lines)}

### Applied Translations

{chr(10).join(breakdown_lines) if breakdown_lines else "   No translations applied"}

   Applied {applied_count} translations

### Files Modified

- Frontend apps: {sync_stats["frontend"]["created"]} created, "
            f"{sync_stats["frontend"]["synced"]} synced"
- Backend: PO files updated

### Next Steps

{chr(10).join(next_steps_lines)}

---
*This PR was automatically generated by the sync_and_translate_language "
            f"management command.*"
"""

    def _create_pr_via_api(
        self,
        repo_path: str,
        branch_name: str,
        lang_code: str,
        iso_code: str,
        sync_stats: dict,
        applied_count: int,
        translation_stats: dict[str, int],
        applied_by_app: dict[str, Any],
        repo_url: str,
    ) -> str:
        """Create PR using GitHub API."""
        client = GitHubAPIClient()
        owner, repo = GitHubAPIClient.parse_repo_url(repo_url)

        client.verify_branch(owner, repo, branch_name, self.stdout)

        git_repo = GitRepository(repo_path)
        main_branch = git_repo._get_main_branch_name()

        return client.create_pull_request(
            owner=owner,
            repo=repo,
            branch_name=branch_name,
            title=f"feat: Add {lang_code} translations via LLM",
            body=self._generate_pr_body(
                lang_code,
                iso_code,
                sync_stats,
                applied_count,
                translation_stats,
                applied_by_app,
            ),
            base=main_branch,
            stdout=self.stdout,
        )
