"""
Django models for the git auto-export plugin.
"""

from django.db import models
from model_utils.models import TimeStampedModel
from opaque_keys.edx.django.models import CourseKeyField


class CourseGitRepository(TimeStampedModel):
    """
    Model to store Git repository information for courses.
    """

    course_key = CourseKeyField(max_length=255, primary_key=True)
    git_url = models.CharField(max_length=255)
    is_export_enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Course Git Repository"
        verbose_name_plural = "Course Git Repositories"
        ordering = ["-created"]

    def __str__(self):
        return f"CourseGitRepository (course_key={self.course_key})"
