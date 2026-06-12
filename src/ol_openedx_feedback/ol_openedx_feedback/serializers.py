"""Serializers for ol_openedx_feedback."""

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey, UsageKey
from rest_framework import serializers

from ol_openedx_feedback.models import BlockFeedback

COMMENT_MAX_LENGTH = 1000


class FeedbackCreateSerializer(serializers.Serializer):
    """Validates a learner-submitted feedback payload and creates a row."""

    course_id = serializers.CharField()
    block_usage_key = serializers.CharField()
    block_type = serializers.CharField(required=False, allow_blank=True, default="")
    block_display_name = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=COMMENT_MAX_LENGTH
    )

    def validate_course_id(self, value):
        """Coerce the course id string into a CourseKey."""
        try:
            return CourseKey.from_string(value)
        except InvalidKeyError as exc:
            raise serializers.ValidationError("Invalid course_id") from exc  # noqa: EM101, TRY003

    def validate_block_usage_key(self, value):
        """Coerce the block usage key string into a UsageKey."""
        try:
            return UsageKey.from_string(value)
        except InvalidKeyError as exc:
            raise serializers.ValidationError("Invalid block_usage_key") from exc  # noqa: EM101, TRY003

    def create(self, validated_data):
        """Create a BlockFeedback row from validated data."""
        return BlockFeedback.objects.create(**validated_data)


class FeedbackReadSerializer(serializers.ModelSerializer):
    """Read representation for the staff/service list endpoint."""

    course_id = serializers.CharField()
    block_usage_key = serializers.CharField()
    user_id = serializers.IntegerField(source="user.id", read_only=True)

    class Meta:
        """Serializer metadata."""

        model = BlockFeedback
        fields = [
            "id",
            "user_id",
            "course_id",
            "course_title",
            "block_usage_key",
            "block_type",
            "block_display_name",
            "rating",
            "comment",
            "created",
        ]
