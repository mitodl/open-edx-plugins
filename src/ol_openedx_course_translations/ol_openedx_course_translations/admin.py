"""Django admin configuration for course translations plugin."""

from statistics import fmean

from django.contrib import admin
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from ol_openedx_course_translations.models import (
    CourseTranslationLog,
    TranslationBenchmark,
    TranslationBenchmarkCandidate,
)
from ol_openedx_course_translations.utils.quality_report import (
    Candidate,
    build_comparative_rows,
    build_rows,
    pick_comparative_winner,
    rank_one_votes,
)

_HOW_IT_WORKS = mark_safe(
    "<details><summary>How this works</summary><ol>"
    "<li>Each translator → validator pair translated the block.</li>"
    "<li>Each judge scored every translation on its own, 1-10 for accuracy, "
    "fluency and terminology.</li>"
    "<li>The candidates placed best across judges went to a shortlist.</li>"
    "<li>Each judge ranked the shortlist side by side. The best average "
    "place wins; a tie for it names no winner.</li>"
    "</ol><p>A comparative-only run skips steps 2 and 3 and ranks every "
    "candidate.</p></details>"
)


def _criteria_values(score):
    """
    Return a score row's three criteria in render order, or None unless
    all three are there.

    The command writes all three or none; a hand-fixed row with some of them
    counts as unscored.
    """
    values = (score.accuracy, score.fluency, score.terminology)
    return values if None not in values else None


def _criteria(values):
    """Render the three criteria joined by slashes."""
    return "/".join(str(value) for value in values)


def _table(headers, rows):
    """Render a plain HTML table; cells are escaped unless already safe."""
    return format_html(
        "<table><tr>{}</tr>{}</table>",
        format_html_join("", "<th>{}</th>", ((header,) for header in headers)),
        format_html_join(
            "",
            "<tr>{}</tr>",
            (
                (format_html_join("", "<td>{}</td>", ((cell,) for cell in row)),)
                for row in rows
            ),
        ),
    )


def _verdict(comparative_rows, votes, ranking_judges):
    """State the comparative pass's winner, or why there is none, in a sentence."""
    winner, reason = pick_comparative_winner(comparative_rows)
    if winner is None:
        return format_html("<p><b>No clear winner:</b> {}.</p>", reason)
    return format_html(
        "<p><b>Winner: {}</b><br>The judges ranked the candidates side by side. "
        "It had the best average place ({}), and {} of {} judge(s) ranked it "
        "alone in first.</p>",
        winner,
        f"{comparative_rows[0].mean_rank:.1f}",
        votes.get(winner, 0),
        ranking_judges,
    )


def _final_ranking(comparative_rows, votes):
    """Render the comparative pass in the verdict's order."""
    judges = sorted({judge for row in comparative_rows for judge in row.positions})
    return format_html(
        "<h3>Final ranking</h3><p>The judges compared these side by side. "
        "Row 1 wins unless tied for first. Each judge column is the place "
        "it gave; a judge with no single first place casts no 1st vote.</p>{}",
        _table(
            ("#", "Candidate", "Avg place", "1st votes", "Judges disagree by", *judges),
            (
                (
                    index,
                    row.candidate,
                    f"{row.mean_rank:.1f}",
                    votes.get(row.candidate, 0),
                    f"{row.spread:.0f} place(s)",
                    *(
                        f"#{row.positions[judge]:.0f}"
                        if judge in row.positions
                        else "—"
                        for judge in judges
                    ),
                )
                for index, row in enumerate(comparative_rows, start=1)
            ),
        ),
    )


def _initial_scoring(scoring_rows, overalls_by_judge, ratings, ranked):
    """Render every candidate's 1-10 overall from each judge."""
    judges = sorted(overalls_by_judge)

    def cell(judge, candidate):
        overall = overalls_by_judge[judge].get(candidate)
        if overall is None:
            # This judge was dropped, or never scored this arm.
            return "—"
        return format_html(
            '<span title="accuracy / fluency / terminology: {}">{}</span>',
            ratings[(judge, candidate)],
            f"{overall:.1f}",
        )

    return format_html(
        "<h3>Initial scoring</h3><p>Each judge scored every candidate on its "
        "own, 1-10. Avg place averages where each judge put the candidate among "
        "its own scores (ties share a place), so every judge counts equally; "
        "the best places went on to be ranked side by side. Hover a score for "
        "accuracy / fluency / terminology.</p>{}",
        _table(
            ("Candidate", "Avg place", "Avg score", *judges, "Ranked side by side"),
            (
                (
                    row.candidate,
                    f"{row.mean_rank:.1f}",
                    f"{row.mean_score:.2f}",
                    *(cell(judge, row.candidate) for judge in judges),
                    "✓" if row.candidate in ranked else "—",
                )
                for row in scoring_rows
            ),
        ),
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


class TranslationBenchmarkCandidateInline(admin.TabularInline):
    """Candidates of a run: which pairings ran and why any were excluded."""

    model = TranslationBenchmarkCandidate
    verbose_name_plural = "Candidates (scores are in Results above)"
    extra = 0
    # The run can be deleted whole; dropping one candidate would silently
    # change its standings.
    can_delete = False
    # No candidate ModelAdmin is registered, so a change link would lead nowhere.
    show_change_link = False
    fields = ("translator", "validator_display", "error")
    readonly_fields = fields

    def get_queryset(self, request):
        """Skip the translated block: each one is large and none is shown."""
        return super().get_queryset(request).defer("translated_content")

    def has_add_permission(self, request, obj=None):  # noqa: ARG002
        """Deny adding rows: runs are produced by the command, never by hand."""
        return False

    @admin.display(description="Validator")
    def validator_display(self, candidate):
        """
        Render an empty validator as 'none' rather than a blank cell.

        Only runs made before validated-only candidates have such rows, and
        they must still read correctly.
        """
        return candidate.validator or "none"


@admin.register(TranslationBenchmark)
class TranslationBenchmarkAdmin(admin.ModelAdmin):
    """One benchmark run and how its candidates placed: deletable, never editable."""

    list_display = (
        "id",
        "target_language",
        "benchmark_block_id",
        "created_at",
        "completed_at",
    )
    list_filter = ("target_language", "benchmark_block_id")
    readonly_fields = (
        "target_language",
        "benchmark_block_id",
        "comparative_only",
        "translators_arg",
        "judges_arg",
        "excluded_judges",
        "created_at",
        "updated_at",
        "completed_at",
        "report",
    )
    fieldsets = (
        (
            "Summary",
            {"fields": ("target_language", "benchmark_block_id", "completed_at")},
        ),
        ("Results", {"fields": ("report",)}),
        (
            "Run settings",
            {
                "classes": ("collapse",),
                "fields": (
                    "comparative_only",
                    "translators_arg",
                    "judges_arg",
                    "excluded_judges",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )
    inlines = (TranslationBenchmarkCandidateInline,)

    def has_add_permission(self, request):  # noqa: ARG002
        """Deny adding rows, as on the inline."""
        return False

    def has_change_permission(self, request, obj=None):  # noqa: ARG002
        """Deny edits: results are a record of what happened."""
        return False

    @admin.display(description="Results")
    def report(self, run):
        """
        Render the verdict, then the comparative pass, then the scoring pass.

        The final ranking comes first and in the verdict's order, so its top
        row is the winner when there is one. The scoring pass follows in the
        order that picked the shortlist; a candidate can lead it and still lose
        head to head, which is why it is a separate table, not the headline.

        What the run set out to do is recorded on the run; what it actually
        produced is read from the rows, and this page renders the rows. The
        two can disagree (a restored dump, a hand-fixed row), so each table
        is shown when its rows exist, whatever ``comparative_only`` says.
        """
        overalls_by_judge: dict[str, dict[Candidate, float]] = {}
        ratings: dict[tuple[str, Candidate], str] = {}
        ranks_by_judge: dict[str, dict[Candidate, int]] = {}
        # Prefetched here rather than on the admin's queryset: that one also
        # feeds the changelist, which would then pull every run's candidates —
        # each carrying a whole translated block — to render a list of dates.
        # translated_content is deferred: a hundred arms carry a whole
        # translated block each and this page renders none of them.
        for candidate in run.candidates.defer("translated_content").prefetch_related(
            "scores"
        ):
            key = Candidate(candidate.translator, candidate.validator)
            for score in candidate.scores.all():
                if values := _criteria_values(score):
                    # A comparative-only run scores nothing, so its rows carry
                    # ranks and null criteria. Averaging those raises, which
                    # would make the run's own admin page unopenable.
                    overalls_by_judge.setdefault(score.judge, {})[key] = fmean(values)
                    ratings[(score.judge, key)] = _criteria(values)
                if score.comparative_rank is not None:
                    ranks_by_judge.setdefault(score.judge, {})[key] = (
                        score.comparative_rank
                    )

        comparative_rows = build_comparative_rows(ranks_by_judge)
        scoring_rows = build_rows(overalls_by_judge)
        if not comparative_rows and not scoring_rows:
            return "No scores recorded."

        votes = rank_one_votes(ranks_by_judge)
        sections = [_verdict(comparative_rows, votes, len(ranks_by_judge))]
        if comparative_rows:
            sections.append(_final_ranking(comparative_rows, votes))
        if scoring_rows:
            ranked = {row.candidate for row in comparative_rows}
            sections.append(
                _initial_scoring(scoring_rows, overalls_by_judge, ratings, ranked)
            )
        sections.append(_HOW_IT_WORKS)
        return format_html_join("", "{}", ((section,) for section in sections))
