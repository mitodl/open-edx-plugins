from django.conf import settings
from django.db import models
from jsonfield import JSONField
from model_utils.models import TimeStampedModel
from opaque_keys.edx.django.models import (
    CourseKeyField,
    UsageKeyField,
)

class CourseSyncMasterOrg(models.Model):
    organization = models.CharField(max_length=255, unique=True)


class CourseSyncMapping(models.Model):
    source_course = CourseKeyField(max_length=255)
    target_courses = model.TextField(null=True, blank=True, help_text="Comma separated list of target course keys")
