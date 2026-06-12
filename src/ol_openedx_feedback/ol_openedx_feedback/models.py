"""Models for the ol_openedx_feedback plugin."""

from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from opaque_keys.edx.django.models import CourseKeyField, UsageKeyField

User = get_user_model()


class BlockFeedback(models.Model):
    """A single learner feedback submission about one course block."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="block_feedback"
    )
    course_id = CourseKeyField(max_length=255, db_index=True)
    course_title = models.CharField(max_length=255, blank=True, default="")
    block_usage_key = UsageKeyField(max_length=255, db_index=True)
    block_type = models.CharField(max_length=64, blank=True, default="")
    block_display_name = models.CharField(max_length=255, blank=True, default="")
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True, default="")
    created = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        """Model metadata."""

        app_label = "ol_openedx_feedback"
        ordering = ["-created"]
        indexes = [models.Index(fields=["course_id", "block_usage_key"])]

    def __str__(self):
        """Human-readable representation of a feedback row."""
        return f"Feedback {self.rating}/5 on {self.block_usage_key} by {self.user_id}"
