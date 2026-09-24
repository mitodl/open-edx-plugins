"""Django admin configuration for course translations plugin."""

from django.contrib import admin
from django.utils.html import format_html, format_html_join

from ol_openedx_course_translations.models import (
    CourseTranslationLog,
    TranslationQualityCandidate,
    TranslationQualityRun,
)
from ol_openedx_course_translations.utils.quality_report import (
    average_overall,
    build_rows,
)


@admin.register(CourseTranslationLog)
class CourseTranslationLogAdmin(admin.ModelAdmin):
    """Admin interface for CourseTranslationLog model."""

    _common_fields = (
        "source_course_language",
        "target_course_language",
        "srt_provider_name",
        "srt_provider_model",
        "content_provider_name",
        "content_provider_model",
    )

    list_display = ("id", "source_course_id", *_common_fields, "created_at")
    list_filter = _common_fields
    readonly_fields = (
        "source_course_id",
        *_common_fields,
        "created_at",
        "command_stats",
    )
    search_fields = ("source_course_id",)


class TranslationQualityCandidateInline(admin.TabularInline):
    """Candidates of a run, with each one's judge scores rendered in place."""

    model = TranslationQualityCandidate
    extra = 0
    can_delete = False
    # No candidate ModelAdmin is registered, so a change link would lead nowhere.
    show_change_link = False
    fields = ("translator", "validator_display", "judge_scores", "error")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):  # noqa: ARG002
        """Deny adding rows: runs are produced by the command, never by hand."""
        return False

    @admin.display(description="Validator")
    def validator_display(self, candidate):
        """Show the unvalidated arm as 'none' rather than an empty cell."""
        return candidate.validator or "none"

    @admin.display(description="Judge scores (accuracy/fluency/terminology)")
    def judge_scores(self, candidate):
        """Render every judge's scores, with the comparative rank if shortlisted."""
        return (
            " · ".join(
                f"{score.judge} {score.accuracy}/{score.fluency}/{score.terminology}"
                + (f" [#{score.comparative_rank}]" if score.comparative_rank else "")
                for score in candidate.scores.all()
            )
            or "—"
        )


@admin.register(TranslationQualityRun)
class TranslationQualityRunAdmin(admin.ModelAdmin):
    """Read-only view of one benchmark run and how its candidates placed."""

    list_display = ("id", "target_language", "benchmark_fixture", "created_at")
    list_filter = ("target_language", "benchmark_fixture")
    readonly_fields = (
        "target_language",
        "benchmark_fixture",
        "translators_arg",
        "judges_arg",
        "created_at",
        "updated_at",
        "report",
    )
    inlines = (TranslationQualityCandidateInline,)

    def get_queryset(self, request):
        """Pull the whole run in one go; the report reads every score."""
        return super().get_queryset(request).prefetch_related("candidates__scores")

    def has_add_permission(self, request):  # noqa: ARG002
        """Deny adding rows: runs are produced by the command, never by hand."""
        return False

    def has_change_permission(self, request, obj=None):  # noqa: ARG002
        """Deny edits: results are a record of what happened."""
        return False

    def has_delete_permission(self, request, obj=None):  # noqa: ARG002
        """Deny deletes: a run is evidence, and deleting it takes its scores."""
        return False

    @admin.display(description="Standings (by mean rank, best first)")
    def report(self, run):
        """
        Render the ranked standings for this run.

        Mean rank and spread are run-wide — a candidate's position depends on
        every other candidate's scores — so they are computed here rather than
        per row in the inline.
        """
        overalls_by_judge: dict[str, dict[str, float]] = {}
        for candidate in run.candidates.all():
            for score in candidate.scores.all():
                overalls_by_judge.setdefault(score.judge, {})[str(candidate)] = (
                    average_overall(
                        {
                            "accuracy": score.accuracy,
                            "fluency": score.fluency,
                            "terminology": score.terminology,
                        }
                    )
                )

        rows = build_rows(overalls_by_judge)
        if not rows:
            return "No scores recorded."

        header = format_html(
            "<tr><th>#</th><th>candidate</th><th>mean rank</th>"
            "<th>mean score</th><th>spread</th><th>judges</th></tr>"
        )
        body = format_html_join(
            "",
            "<tr><td>{}</td><td>{}</td><td>{:.2f}</td><td>{:.2f}</td>"
            "<td>{:.1f}</td><td>{}</td></tr>",
            (
                (
                    position,
                    row.candidate,
                    row.mean_rank,
                    row.mean_score,
                    row.spread,
                    row.judges,
                )
                for position, row in enumerate(rows, start=1)
            ),
        )
        return format_html("<table>{}{}</table>", header, body)
