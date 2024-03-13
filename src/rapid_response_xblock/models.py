"""
Rapid Response block models
"""


from django.conf import settings
from django.db import models

from jsonfield import JSONField
from model_utils.models import TimeStampedModel
from opaque_keys.edx.django.models import (
    CourseKeyField,
    UsageKeyField,
)


class RapidResponseRun(models.Model):
    """
    Stores information for a group of RapidResponseSubmission objects
    """
    problem_usage_key = UsageKeyField(db_index=True, max_length=255)
    course_key = CourseKeyField(db_index=True, max_length=255)
    open = models.BooleanField(default=False, null=False)

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return (
            "id={id} created={created} problem_usage_key={problem_usage_key} "
            "course_key={course_key} open={open}".format(
                id=self.id,
                created=self.created.isoformat(),
                problem_usage_key=self.problem_usage_key,
                course_key=self.course_key,
                open=self.open,
            )
        )


class RapidResponseSubmission(TimeStampedModel):
    """
    Stores the student submissions for a problem that is
    configured with rapid response
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        db_index=True,
    )
    run = models.ForeignKey(
        RapidResponseRun,
        on_delete=models.SET_NULL,
        null=True,
        db_index=True
    )
    answer_id = models.CharField(null=True, max_length=255)
    answer_text = models.CharField(null=True, max_length=4096)
    event = JSONField()

    def __str__(self):
        return (
            "user={user} run={run} answer_id={answer_id}".format(
                user=self.user,
                run=self.run,
                answer_id=self.answer_id,
            )
        )
