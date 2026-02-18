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
