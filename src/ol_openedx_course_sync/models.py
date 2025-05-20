"""
Models for ol-openedx-course-sync plugin
"""

from django.core.exceptions import ValidationError
from django.db import models
from opaque_keys.edx.django.models import (
    CourseKeyField,
)


class CourseSyncOrganization(models.Model):
    """
    Model for source course organizations

    Any source course that is part of this organization
    will sync changes with the child/rerun courses. This model
    will help us exclude any organizations where we don't
    want to sync source course.
    """

    organization = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "ol_openedx_course_sync"

    def __str__(self):
        return f"{self.organization} Course Sync Parent Org"


class CourseSyncMap(models.Model):
    """
    Model to keep track of source and target courses.
    """

    source_course = CourseKeyField(max_length=255)
    target_course = CourseKeyField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "ol_openedx_course_sync"

    def __str__(self):
        return f"{self.source_course} Course Sync Map"

    def save(self, *args, **kwargs):
        """
        Override save method to perform custom validations.
        """
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        """
        Override clean method to perform custom validations.
        """
        super().clean()

        conflicting_target = CourseSyncMap.objects.filter(
            target_course=self.source_course
        ).first()
        if conflicting_target:
            raise ValidationError(
                {
                    "source_course": f"This course is already used as target course of: "  # noqa: E501
                    f"{conflicting_target.source_course}"
                }
            )

        conflicting_source = CourseSyncMap.objects.filter(
            source_course=self.target_course
        ).first()
        if conflicting_source:
            raise ValidationError(
                {"target_course": "This course is already a source course"}
            )
