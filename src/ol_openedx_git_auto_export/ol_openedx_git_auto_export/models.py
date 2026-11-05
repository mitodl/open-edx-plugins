"""
Django models for the git auto-export plugin.
"""

from django.db import models
from model_utils.models import TimeStampedModel
from opaque_keys.edx.django.models import LearningContextKeyField


class ContentGitRepository(TimeStampedModel):
    """
    Model to store Git repository information for courses and libraries.

    This model uses LearningContextKeyField which supports both CourseKey
    and LibraryLocator, making it suitable for both courses and libraries.
    """

    content_key = LearningContextKeyField(max_length=255, primary_key=True)
    git_url = models.CharField(max_length=255)
    is_export_enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Content Git Repository"
        verbose_name_plural = "Content Git Repositories"
        ordering = ["-created"]

    def __str__(self):
        return f"ContentGitRepository (content_key={self.content_key})"


class ExportStatus(models.TextChoices):
    """Outcome of one export run; in_progress until it finishes."""

    # Left as is by a run killed mid-export (OOM, time limit, pod restart).
    IN_PROGRESS = "in_progress", "In progress"
    SUCCESS = "success", "Success"
    NO_CHANGES = "no_changes", "No changes"
    SKIPPED_DISABLED = "skipped_disabled", "Skipped: export disabled"
    NOT_FOUND = "not_found", "Content not found"
    NO_REPO = "no_repo", "No repository"
    REPO_CREATION_FAILED = "repo_creation_failed", "Repository creation failed"
    FAILED = "failed", "Failed"


class ContentGitExportLog(TimeStampedModel):
    """
    One row per export run, kept so intermittent failures show as a pattern.
    The newest row per content_key is its current status.
    """

    # Not a FK: not_found and no_repo rows have no ContentGitRepository.
    content_key = LearningContextKeyField(max_length=255)
    status = models.CharField(max_length=32, choices=ExportStatus.choices)
    user = models.CharField(max_length=150, blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True)
    git_url = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)
    git_output = models.TextField(blank=True)
    # Timestamped log lines, written as the run goes.
    log = models.TextField(blank=True)

    class Meta:
        verbose_name = "Content Git Export Log"
        verbose_name_plural = "Content Git Export Logs"
        ordering = ["-created"]
        indexes = [models.Index(fields=["content_key", "-created"])]

    def __str__(self):
        return f"ContentGitExportLog ({self.content_key}: {self.status})"
