"""Models for course translations plugin"""

from django.db import models
from opaque_keys.edx.django.models import CourseKeyField


class CourseTranslationLog(models.Model):
    """Log entry for course translation operations."""

    source_course_id = CourseKeyField(max_length=255, db_index=True)
    source_course_language = models.CharField(
        max_length=10,
        help_text="Source language code (e.g., 'EN')",
    )
    target_course_language = models.CharField(
        max_length=10,
        help_text="Target language code for translation (e.g., 'FR')",
    )
    srt_provider_name = models.CharField(
        max_length=100,
        help_text="LLM Provider used for SRT translation",
    )
    srt_provider_model = models.CharField(
        max_length=100,
        blank=True,
        help_text="LLM provider model used for SRT translation",
    )
    content_provider_name = models.CharField(
        max_length=100,
        help_text="LLM Provider used for content translation",
    )
    content_provider_model = models.CharField(
        max_length=100,
        blank=True,
        help_text="LLM provider model used for content translation",
    )
    command_stats = models.TextField(
        blank=True, help_text="Logs from the translation command"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        """Meta options for CourseTranslationLog."""

        app_label = "ol_openedx_course_translations"

    def __str__(self):
        """Return a string representation of the translation log."""
        return (
            f"{self.source_course_id} "
            f"({self.source_course_language} → {self.target_course_language})"
        )


class TranslationQualityRun(models.Model):
    """One invocation of the rate_translation_quality command for a language."""

    target_language = models.CharField(
        max_length=10,
        db_index=True,
        help_text="Target language code for this run",
    )
    benchmark_fixture = models.CharField(
        max_length=255,
        help_text="Benchmark file this run translated",
    )
    translators_arg = models.TextField(
        help_text="Resolved translator roster actually used",
    )
    judges_arg = models.TextField(
        help_text="Resolved judge roster actually used",
    )
    excluded_judges = models.TextField(
        blank=True,
        help_text="Judges dropped from scoring, and why",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for TranslationQualityRun."""

        app_label = "ol_openedx_course_translations"

    def __str__(self):
        """Return a string representation of the run."""
        return f"Translation quality run {self.pk} ({self.target_language})"


class TranslationQualityCandidate(models.Model):
    """One translator/validator pairing under test within a run."""

    run = models.ForeignKey(
        TranslationQualityRun,
        on_delete=models.CASCADE,
        related_name="candidates",
    )
    translator = models.CharField(
        max_length=200,
        help_text="Provider/model that translated",
    )
    validator = models.CharField(
        max_length=200,
        blank=True,
        help_text="Provider/model that reviewed; blank if none",
    )
    error = models.TextField(
        blank=True,
        help_text="Why this candidate was excluded, if it was",
    )

    class Meta:
        """Meta options for TranslationQualityCandidate."""

        app_label = "ol_openedx_course_translations"
        constraints = [
            models.UniqueConstraint(
                fields=["run", "translator", "validator"],
                name="unique_candidate_per_run",
            )
        ]

    def __str__(self):
        """Return a string representation of the candidate."""
        return f"{self.translator} → {self.validator or 'none'}"


class TranslationQualityScore(models.Model):
    """One judge's assessment of one candidate."""

    candidate = models.ForeignKey(
        TranslationQualityCandidate,
        on_delete=models.CASCADE,
        related_name="scores",
    )
    judge = models.CharField(
        max_length=200,
        help_text="Provider/model that scored this candidate",
    )
    accuracy = models.PositiveSmallIntegerField(
        help_text="Meaning preserved, 1-10",
    )
    fluency = models.PositiveSmallIntegerField(
        help_text="Reads naturally to a native reader, 1-10",
    )
    terminology = models.PositiveSmallIntegerField(
        help_text="Terms and proper nouns handled, 1-10",
    )
    justification = models.TextField(
        blank=True,
        help_text="The judge's rationale, truncated",
    )
    comparative_rank = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Rank this judge gave; null if it did not rank this",
    )
    comparative_label = models.CharField(
        max_length=2,
        blank=True,
        help_text="Label this judge saw; blank if it did not rank this",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Meta options for TranslationQualityScore."""

        app_label = "ol_openedx_course_translations"
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "judge"],
                name="unique_score_per_candidate_and_judge",
            )
        ]

    def __str__(self):
        """Return a string representation of the score."""
        return f"{self.judge} on {self.candidate}"
