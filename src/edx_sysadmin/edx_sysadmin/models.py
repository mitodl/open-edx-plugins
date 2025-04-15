"""
Database models for edx_sysadmin.
"""

from django.db import models
from jsonfield.fields import JSONField
from opaque_keys.edx.django.models import CourseKeyField


class CourseGitLog(models.Model):  # noqa: DJ008
    """CourseGitLog to store git-logs of courses imported from github"""

    course_id = CourseKeyField(max_length=255, db_index=True)
    course_import_log = JSONField(null=True, blank=True)
    git_log = models.TextField(null=True, blank=True)  # noqa: DJ001
    repo_dir = models.CharField(max_length=255)
    commit = models.CharField(max_length=40, null=True)  # noqa: DJ001
    author = models.CharField(max_length=255)
    created = models.DateTimeField(auto_now_add=True, null=True)
