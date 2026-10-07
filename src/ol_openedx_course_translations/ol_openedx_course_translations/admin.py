"""Django admin configuration for course translations plugin."""

from statistics import fmean

from django.contrib import admin
from django.utils.html import format_html, format_html_join

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
)


def _criteria_values(score):
    """
    Return a score row's three criteria in render order, or None unless
    all three are there.

    All three or none is what the command writes, but the standings and the
    inline both have to decide what a row with some of them is, and two
    spellings of that question would let a hand-fixed row render on one and
    vanish from the other.
    """
    values = (score.accuracy, score.fluency, score.terminology)
    return values if None not in values else None


def _criteria(values):
    """Render the three criteria joined by slashes, or an em dash."""
    return "/".join(str(value) for value in values) if values else "—"


def _judge_cell(row, judge, ratings, ranks_by_judge):
    """
    One judge's view of one candidate: position, raw scores, and its rank.

    An em dash for the whole cell means this judge never placed the
    candidate; an em dash in the scores slot means ``_criteria_values``
    found nothing to show.
    """
    position = row.positions.get(judge)
    if position is None:
        # This judge was dropped, or never placed this arm.
        return "—"
    rank = ranks_by_judge.get(judge, {}).get(row.candidate)
    scores = ratings.get((judge, row.candidate), "—")
    cell = f"{position:.1f} · {scores}"
    return cell if rank is None else f"{cell} · #{rank}"


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
    """Candidates of a run, with each one's judge scores rendered in place."""

    model = TranslationBenchmarkCandidate
    extra = 0
    can_delete = False
    # No candidate ModelAdmin is registered, so a change link would lead nowhere.
    show_change_link = False
    fields = ("translator", "validator_display", "judge_scores", "error")
    readonly_fields = fields

    def get_queryset(self, request):
        """
        Pull each candidate's scores with it.

        The inline gets its own queryset, so the parent's prefetch does not
        reach here and judge_scores would otherwise query once per row.
        """
        return (
            super()
            .get_queryset(request)
            .defer("translated_content")
            .prefetch_related("scores")
        )

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

    @admin.display(description="Judge scores (accuracy/fluency/terminology)")
    def judge_scores(self, candidate):
        """
        Render every judge's scores, with its comparative rank when it has one.

        A row ``_criteria_values`` rejects reads as an em dash rather than
        as "None/None/None".
        """
        return (
            " · ".join(
                f"{score.judge} {_criteria(_criteria_values(score))}"
                + (
                    f" [#{score.comparative_rank}]"
                    if score.comparative_rank is not None
                    else ""
                )
                for score in candidate.scores.all()
            )
            or "—"
        )


@admin.register(TranslationBenchmark)
class TranslationBenchmarkAdmin(admin.ModelAdmin):
    """Read-only view of one benchmark run and how its candidates placed."""

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
    inlines = (TranslationBenchmarkCandidateInline,)

    def has_add_permission(self, request):  # noqa: ARG002
        """Deny adding rows, as on the inline."""
        return False

    def has_change_permission(self, request, obj=None):  # noqa: ARG002
        """
        Deny edits: results are a record of what happened.

        Deleting a whole run is allowed, so smoke tests and interrupted runs can
        be cleaned up. The inline keeps can_delete off, because removing one
        candidate would silently change the run's standings.
        """
        return False

    @admin.display(description="Standings (by mean rank, best first)")
    def report(self, run):
        """
        Render the ranked standings for this run, judge by judge.

        Mean rank and spread are run-wide — a candidate's position depends on
        every other candidate's scores — so they are computed here rather than
        per row in the inline. Each judge also gets its own column, because
        the aggregate hides the two things worth seeing: which judge a
        candidate's placing came from, and whether the comparative pass
        agreed with the scoring pass.

        What the run set out to do is recorded on the run; what it actually
        produced is read from the rows, and this page renders the rows. The
        two can disagree — a restored dump, a hand-fixed row — and a page
        that believed the flag over its own data would either promise score
        columns it cannot fill, or bury the scores it is holding under a
        comparative table.

        The judge columns are the union of the two passes, because a judge
        that only ranked still decided the verdict. In a two-pass run the
        two sets normally coincide — ``_rank`` is handed
        ``scoring.excluded_judges`` and skips them, and ``handle`` aborts
        when nothing scored at all — so the union usually adds nothing. A
        mode that ranks an existing run is where it earns its keep.
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

        # The verdict is always the comparative pass's. When the scoring pass
        # ran it orders the table; when it was skipped the comparative ranks
        # are the table.
        comparative_rows = build_comparative_rows(ranks_by_judge)
        # One question, asked once: did this run's rows record any scores?
        # The table, the columns and the legend all follow that answer, so
        # they cannot end up describing different runs from each other.
        rows = build_rows(overalls_by_judge) or comparative_rows
        if not rows:
            return "No scores recorded."

        # Union, not a choice: a judge that only ranked still decided the
        # verdict, and a page that gave it no column would name a winner
        # nothing on it accounts for.
        judges = sorted(overalls_by_judge.keys() | ranks_by_judge.keys())
        verdict, reason = pick_comparative_winner(comparative_rows)

        # Numbers are formatted before they reach format_html_join: it escapes
        # each argument into a SafeString first, which no longer accepts a
        # numeric format spec.
        body = format_html_join(
            "",
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td>{}</tr>",
            (
                (
                    position,
                    row.candidate,
                    f"{row.mean_rank:.2f}",
                    "—" if row.mean_score is None else f"{row.mean_score:.2f}",
                    f"{row.spread:.1f}",
                    format_html_join(
                        "",
                        "<td>{}</td>",
                        (
                            (_judge_cell(row, judge, ratings, ranks_by_judge),)
                            for judge in judges
                        ),
                    ),
                )
                for position, row in enumerate(rows, start=1)
            ),
        )
        if overalls_by_judge:
            legend = (
                "Each judge column reads position · "
                "accuracy/fluency/terminology · #comparative rank. Position is "
                "where that judge placed the candidate when scoring it alone; "
                "#rank is where it placed the candidate against the shortlist. "
                "Only shortlisted candidates carry a #rank."
            )
        else:
            # Nothing was scored alone and no shortlist was taken, so the
            # two-pass wording would describe a pass this run never ran.
            legend = (
                "This run was ranked comparatively only. Each judge column "
                "reads position · — · #comparative rank, where the position "
                "is that rank: there are no scores, and every candidate was "
                "ranked."
            )

        return format_html(
            "<p><b>Verdict:</b> {} — {}</p><p>{}</p>"
            "<table><tr><th>#</th><th>candidate</th><th>mean rank</th>"
            "<th>mean score</th><th>spread</th>{}</tr>{}</table>",
            verdict or "no clear winner",
            reason,
            legend,
            format_html_join("", "<th>{}</th>", ((judge,) for judge in judges)),
            body,
        )
