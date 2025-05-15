"""
Models for ol-openedx-course-sync plugin
"""

from django.core.exceptions import ValidationError
from django.db import models
from opaque_keys.edx.django.models import (
    CourseKeyField,
)


class CourseSyncParentOrg(models.Model):
    """
    Model for source course organizations

    Any source course that is part of this organization
    will sync changes with the child/rerun courses. This model
    will help us exclude any organizations, where we don't
    want to sync source course.
    """

    organization = models.CharField(max_length=255, unique=True)

    class Meta:
        app_label = "ol_openedx_course_sync"

    def __str__(self):
        return f"{self.organization} Course Sync Parent Org"


class CourseSyncMap(models.Model):
    """
    Model to keep track of source and target courses.

    Any changes in the source course sync with the target courses.
    Target courses are autopopulated for all the reruns of source
    courses that are part of any organization added in `CourseSyncParentOrg`.
    """

    source_course = CourseKeyField(max_length=255, unique=True)
    target_courses = models.TextField(
        blank=True, help_text="Comma separated list of target course keys"
    )

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

        conflicting_targets = CourseSyncMap.objects.filter(
            target_courses__contains=self.source_course
        )
        if conflicting_targets:
            raise ValidationError(
                {
                    "source_course": f"This course is already used as target course of: "  # noqa: E501
                    f"{', '.join(str(ct.source_course) for ct in conflicting_targets)}"
                }
            )

        conflicting_sources = CourseSyncMap.objects.filter(
            source_course__in=self.target_course_keys
        )
        if conflicting_sources:
            raise ValidationError(
                {
                    "target_courses": f"These course(s) are already used as source courses: "  # noqa:E501
                    f"{', '.join(str(cs.source_course) for cs in conflicting_sources)}"
                }
            )

        if self.target_course_keys:
            query = models.Q()
            for key in self.target_course_keys:
                query |= models.Q(**{"target_courses__contains": key})
            duplicate_targets = CourseSyncMap.objects.filter(query)

            if self.pk:
                duplicate_targets = duplicate_targets.exclude(pk=self.pk)

            if duplicate_targets:
                raise ValidationError(
                    {
                        "target_courses": f"Some of these course(s) are already used as target course(s) for: "  # noqa:E501
                        f"{', '.join(str(dt.source_course) for dt in duplicate_targets)}"  # noqa:E501
                    }
                )

    @property
    def target_course_keys(self):
        """
        Returns a list of target course keys.
        """
        return [key for key in self.target_courses.strip().split(",") if key]
