"""
Django models for the git auto-export plugin.

This module defines the CourseGitHubRepository model which stores the mapping between
OpenedX courses and their GitHub repositories for automated export functionality.
"""

from django.db import models
from model_utils.models import TimeStampedModel
from opaque_keys.edx.django.models import CourseKeyField


class CourseGitHubRepository(TimeStampedModel):
    """
    Model to store Git repository information for courses.
    """

    course_key = CourseKeyField(max_length=255, primary_key=True)
    git_url = models.CharField(max_length=255)
    is_export_enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Course GitHub Repository"
        verbose_name_plural = "Course GitHub Repositories"
        ordering = ["-created"]

    def __str__(self):
        return f"CourseGitHubRepository (course_key={self.course_key})"
