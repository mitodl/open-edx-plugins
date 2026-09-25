import logging
import random
import time
from dataclasses import dataclass

from celery import group
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ol_openedx_course_translations.models import (
    TranslationQualityCandidate,
    TranslationQualityRun,
    TranslationQualityScore,
)
from ol_openedx_course_translations.providers.llm_providers import COMPARATIVE_LABELS
from ol_openedx_course_translations.tasks import (
    benchmark_rank_task,
    benchmark_score_task,
    benchmark_translate_task,
    benchmark_validate_task,
)
from ol_openedx_course_translations.utils.benchmark import (
    BENCHMARK_PATH,
    Benchmark,
    BenchmarkError,
    count_unchanged_units,
    read_benchmark,
)
from ol_openedx_course_translations.utils.course_translations import (
    parse_and_validate_provider_spec,
)
from ol_openedx_course_translations.utils.quality_report import (
    SHORTLIST_CAP,
    Candidate,
    Rating,
    average_overall,
    build_rows,
    pick_winner,
    rank_one_votes,
    select_shortlist,
)

logger = logging.getLogger(__name__)

# Rough characters per token, for the pre-flight size estimate only.
CHARS_PER_TOKEN = 4

# Stage polling. The stage timeout matches translate_course's: a 10-translator
# run is tens of minutes of work, and the group must not be abandoned mid-flight.
BENCHMARK_POLL_INTERVAL = 2
BENCHMARK_STAGE_TIMEOUT = 7200


@dataclass(frozen=True)
class Arm:
    """One candidate's content, or why it has none."""

    content: str | None = None
    error: str = ""
    elements: int = 0
    # Units in this arm's content still identical to the English source.
    # Diagnostic only: some units are identical in any language, so this is
    # shown, never scored. None when it could not be measured.
    unchanged_units: int | None = None

    @property
    def usable(self) -> bool:
        """Whether this arm has content a judge can score."""
        return self.content is not None and not self.error


@dataclass(frozen=True)
class ScoringPass:
    """What the scoring pass produced, and which judges it lost."""

    overalls: dict[str, dict[Candidate, float]]
    ratings: dict[tuple[str, Candidate], Rating]
    # judge -> why it was dropped, kept so a stored run records the reason and
    # not merely the absence of its scores.
    excluded_judges: dict[str, str]


@dataclass(frozen=True)
class RankingPass:
    """What the comparative pass produced, and how many judges attempted it."""

    ranks: dict[str, dict[Candidate, int]]
    labels: dict[tuple[str, Candidate], str]
    attempted: int


class Command(BaseCommand):
    """Rate translation quality across translator/validator/judge combinations."""

    help = (
        "Translate a fixed benchmark unit with every translator, validate each "
        "translation with every validator, and have every judge rate the results."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--target-language",
            required=True,
            help="Language code to translate the benchmark into (e.g. 'hi')",
        )
        parser.add_argument(
            "--translators",
            default="",
            help=(
                "Comma-separated PROVIDER or PROVIDER/MODEL specs used both as "
                "translators and as validators. Defaults to every provider with "
                "an api_key, at its default_model."
            ),
        )
        parser.add_argument(
            "--judges",
            default="",
            help=(
                "Comma-separated PROVIDER or PROVIDER/MODEL specs that score the "
                "candidates. Defaults to every provider with an api_key."
            ),
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip the run-size confirmation prompt.",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Run the benchmark end to end."""
        target_language = options["target_language"]
        self._validate_language(target_language)

        translators = self._resolve_roster(options["translators"], "translator")
        judges = self._resolve_roster(options["judges"], "judge")
        if not translators:
            msg = "No usable translators. Configure an api_key or pass --translators."
            raise CommandError(msg)
        if not judges:
            msg = "No usable judges. Configure an api_key or pass --judges."
            raise CommandError(msg)

        try:
            benchmark = read_benchmark()
        except BenchmarkError as error:
            raise CommandError(str(error)) from error

        self._confirm_run(
            translators=translators,
            judges=judges,
            benchmark=benchmark,
            skip_prompt=options["yes"],
        )

        run = TranslationQualityRun.objects.create(
            target_language=target_language,
            benchmark_fixture=BENCHMARK_PATH.name,
            translators_arg=",".join(translators),
            judges_arg=",".join(judges),
        )
        rows = self._create_rows(run, translators)

        failed_translators = self._translate(rows, translators, target_language)
        self._validate(rows, translators, failed_translators, target_language)
        arms = self._load_arms(run, benchmark)

        scoring = self._score(rows, arms, judges, target_language)
        if not scoring.overalls:
            self._report_broken_arms(arms)
            run.excluded_judges = self._format_exclusions(scoring)
            run.save(update_fields=["excluded_judges"])
            msg = f"No candidate was scored by any judge (run {run.pk})."
            raise CommandError(msg)

        report_rows = build_rows(scoring.overalls)
        shortlist = select_shortlist(report_rows)
        ranking = self._rank(
            shortlist, rows, judges, scoring.excluded_judges, target_language
        )

        # Reported before the scores are written: the translations are already
        # safe on their rows, and a write failure should not also cost the
        # standings the run paid for.
        self._report(report_rows, arms, scoring, ranking)

        with transaction.atomic():
            self._persist_scores(run, rows, scoring, ranking)
        self.stdout.write(
            f"\nStored as run {run.pk}; see the Django admin for details."
        )

    # ---------------------------------------------------------------- setup

    def _validate_language(self, target_language: str) -> None:
        supported = settings.COURSE_TRANSLATIONS_SUPPORTED_LANGUAGES
        if target_language not in supported:
            msg = (
                f"Unsupported target language: {target_language}. "
                f"Supported languages: {', '.join(sorted(supported))}"
            )
            raise CommandError(msg)

    def _resolve_roster(self, raw: str, role: str) -> list[str]:
        """
        Turn a roster argument into canonical ``provider/model`` specs.

        A provider with no ``api_key`` is skipped with a note, so a partly
        configured environment still produces a usable comparison. A provider
        named on the command line but absent from settings is fatal instead:
        skipping it would answer a different question than the one asked.
        """
        providers = settings.TRANSLATIONS_PROVIDERS
        requested = [entry.strip() for entry in raw.split(",") if entry.strip()]
        explicit = bool(requested)
        if not explicit:
            # TRANSLATIONS_PROVIDERS also holds "default_provider", a plain
            # string, which is not a provider entry.
            requested = [
                name for name, config in providers.items() if isinstance(config, dict)
            ]

        resolved = []
        for entry in requested:
            provider_name = entry.split("/", 1)[0].lower()
            config = providers.get(provider_name)
            if not isinstance(config, dict):
                if explicit:
                    msg = (
                        f"Unknown {role} provider '{provider_name}'. Configured "
                        f"providers: {', '.join(sorted(providers))}"
                    )
                    raise CommandError(msg)
                continue
            if not config.get("api_key"):
                self.stdout.write(
                    self.style.WARNING(f"⊘ skipped {role} {entry}: no api_key")
                )
                continue
            name, model = parse_and_validate_provider_spec(entry)
            resolved.append(f"{name}/{model}")

        # 'openai' and 'openai/<default_model>' resolve to the same spec, and a
        # repeat would collide on the per-run unique constraint.
        return list(dict.fromkeys(resolved))

    def _confirm_run(
        self,
        *,
        translators: list[str],
        judges: list[str],
        benchmark: Benchmark,
        skip_prompt: bool,
    ) -> None:
        """Show the size of the run before any request is made."""
        candidates = len(translators) * (len(translators) + 1)
        calls = {
            "translations": len(translators),
            "validations": len(translators) * len(translators),
            "scoring": candidates * len(judges),
            "ranking": len(judges),
        }
        payload = len(benchmark.content)
        # What each call carries: a translation sends the extracted text units
        # (roughly one source's worth), a validation sends source + translation,
        # a score sends source + one candidate, a ranking sends source + the
        # shortlist. Sized for the widest shortlist the cap allows and for every
        # judge reaching the ranking pass, so the figure shown is an upper bound
        # rather than one a dropped judge or a short shortlist can exceed.
        approx_tokens = (
            payload
            * (
                calls["translations"]
                + calls["validations"] * 2
                + calls["scoring"] * 2
                + calls["ranking"] * (1 + SHORTLIST_CAP)
            )
            // CHARS_PER_TOKEN
        )

        self.stdout.write(
            f"\nBenchmark:   {BENCHMARK_PATH.name}"
            f"\nTranslators: {', '.join(translators)}"
            f"\nJudges:      {', '.join(judges)}"
            f"\nCandidates:  {candidates}"
            f"\nLLM calls:   ~{sum(calls.values())} "
            f"({calls['translations']} translate, {calls['validations']} validate, "
            f"{calls['scoring']} score, {calls['ranking']} rank)"
            f"\nInput tokens: ~{approx_tokens:,} (rough estimate)\n"
        )
        if skip_prompt:
            return
        try:
            answer = input("Proceed? y/n: ").strip().lower()
        except EOFError:
            msg = "stdin is not a terminal; pass --yes to run unattended."
            raise CommandError(msg) from None
        if answer not in ("y", "yes"):
            msg = "Aborted before any request was made."
            raise CommandError(msg)

    # ------------------------------------------------------------ execution

    def _dispatch(self, signatures: list, header: str) -> list:
        """
        Run a stage as one Celery group and wait for it.

        ``propagate=False`` so a task that exhausted its retries comes back as
        a result to record rather than an exception that ends the stage: one
        provider failing must not cost the work already paid for.
        """
        if not signatures:
            return []

        self.stdout.write(f"{header}: {len(signatures)} task(s)...")
        result = group(signatures).apply_async()
        while not result.ready():
            done = sum(1 for child in result.results if child.ready())
            self.stdout.write(f"  {done}/{len(signatures)} done\r", ending="")
            self.stdout.flush()
            time.sleep(BENCHMARK_POLL_INTERVAL)
        return result.get(timeout=BENCHMARK_STAGE_TIMEOUT, propagate=False)

    @staticmethod
    def _outcome(result) -> tuple[bool, str]:
        """Read a task result, treating anything unexpected as a failure."""
        if not isinstance(result, dict):
            return False, f"{type(result).__name__}: {result}"
        if result.get("status") != "success":
            return False, str(result.get("error", "unknown error"))
        return True, ""

    def _create_rows(
        self, run: TranslationQualityRun, translators: list[str]
    ) -> dict[Candidate, TranslationQualityCandidate]:
        """Create every arm up front, so tasks can address rows by id."""
        return {
            Candidate(
                translator, validator
            ): TranslationQualityCandidate.objects.create(
                run=run, translator=translator, validator=validator
            )
            for translator in translators
            for validator in ["", *translators]
        }

    def _translate(
        self,
        rows: dict[Candidate, TranslationQualityCandidate],
        translators: list[str],
        target_language: str,
    ) -> set[str]:
        """Translate once per translator; returns the translators that failed."""
        signatures = [
            benchmark_translate_task.s(
                rows[Candidate(translator)].pk, translator, target_language
            )
            for translator in translators
        ]
        failed = set()
        for translator, result in zip(
            translators, self._dispatch(signatures, "Translating"), strict=False
        ):
            succeeded, reason = self._outcome(result)
            if not succeeded:
                failed.add(translator)
                self.stdout.write(
                    self.style.WARNING(f"⊘ translator {translator}: {reason}")
                )
        return failed

    def _validate(
        self,
        rows: dict[Candidate, TranslationQualityCandidate],
        translators: list[str],
        failed_translators: set[str],
        target_language: str,
    ) -> None:
        """Review each usable translation with every validator."""
        signatures: list = []
        for translator in translators:
            if translator in failed_translators:
                # The arms of a failed translation have nothing to review.
                for validator in translators:
                    arm = rows[Candidate(translator, validator)]
                    arm.error = "translation failed"
                    arm.save(update_fields=["error"])
                continue
            signatures.extend(
                benchmark_validate_task.s(
                    rows[Candidate(translator, validator)].pk,
                    rows[Candidate(translator)].pk,
                    validator,
                    target_language,
                )
                for validator in translators
            )
        self._dispatch(signatures, "Validating")

    def _load_arms(
        self, run: TranslationQualityRun, benchmark: Benchmark
    ) -> dict[Candidate, Arm]:
        """Read back what the tasks wrote, with the diagnostic recomputed."""
        arms = {}
        for row in run.candidates.all():
            content = row.translated_content or None
            arms[Candidate(row.translator, row.validator)] = Arm(
                content=content,
                error=row.error,
                unchanged_units=(
                    count_unchanged_units(content, benchmark) if content else None
                ),
            )
        return arms

    def _score(
        self,
        rows: dict[Candidate, TranslationQualityCandidate],
        arms: dict[Candidate, Arm],
        judges: list[str],
        target_language: str,
    ) -> ScoringPass:
        """
        Have every judge score every usable candidate, one candidate per call.

        A judge that fails anywhere is dropped from the whole scoring pass, so
        every candidate ends up ranked over an identical set of judges. That is
        a decision over the whole stage, which is why the tasks return their
        ratings instead of writing them.
        """
        usable = [key for key, arm in arms.items() if arm.usable]
        signatures = [
            benchmark_score_task.s(rows[key].pk, judge, target_language)
            for judge in judges
            for key in usable
        ]
        results = self._dispatch(
            signatures,
            f"Scoring {len(usable)} candidate(s) against {len(judges)} judge(s)",
        )

        by_id = {rows[key].pk: key for key in usable}
        reasons: dict[str, str] = {}
        collected: list[tuple[str, Candidate, Rating]] = []
        for result in results:
            succeeded, reason = self._outcome(result)
            judge = str(result.get("judge", "")) if isinstance(result, dict) else ""
            if not succeeded:
                if judge and judge not in reasons:
                    reasons[judge] = reason
                continue
            key = by_id[result["candidate_id"]]
            collected.append(
                (judge, key, Rating(result["scores"], result["justification"]))
            )

        for judge, reason in sorted(reasons.items()):
            self.stdout.write(self.style.WARNING(f"⊘ judge {judge} dropped: {reason}"))

        overalls: dict[str, dict[Candidate, float]] = {}
        ratings: dict[tuple[str, Candidate], Rating] = {}
        for judge, key, rating in collected:
            if judge in reasons:
                continue
            overalls.setdefault(judge, {})[key] = average_overall(rating.scores)
            ratings[(judge, key)] = rating
        return ScoringPass(overalls, ratings, dict(sorted(reasons.items())))

    def _rank(
        self,
        shortlist,
        rows: dict[Candidate, TranslationQualityCandidate],
        judges: list[str],
        excluded_judges: dict[str, str],
        target_language: str,
    ) -> RankingPass:
        """
        Have each judge rank the shortlist side by side, shuffled per judge.

        Shuffling per judge rather than once per run means a candidate does not
        sit in the same prompt position for everyone, so presentation order
        cannot favour it consistently.
        """
        ranking_judges = [judge for judge in judges if judge not in excluded_judges]
        if len(shortlist) < 2 or not ranking_judges:  # noqa: PLR2004
            return RankingPass({}, {}, 0)

        by_id = {rows[row.candidate].pk: row.candidate for row in shortlist}
        signatures: list = []
        label_maps: dict[str, dict[str, Candidate]] = {}
        for judge in ranking_judges:
            order = [row.candidate for row in shortlist]
            random.shuffle(order)
            label_maps[judge] = dict(zip(COMPARATIVE_LABELS, order, strict=False))
            signatures.append(
                benchmark_rank_task.s(
                    judge,
                    {label: rows[key].pk for label, key in label_maps[judge].items()},
                    target_language,
                )
            )

        ranks: dict[str, dict[Candidate, int]] = {}
        labels: dict[tuple[str, Candidate], str] = {}
        for result in self._dispatch(signatures, f"Ranking the top {len(shortlist)}"):
            succeeded, reason = self._outcome(result)
            judge = str(result.get("judge", "")) if isinstance(result, dict) else ""
            if not succeeded:
                self.stdout.write(
                    self.style.WARNING(f"⊘ judge {judge} ranking failed: {reason}")
                )
                continue
            ranks[judge] = {
                by_id[int(candidate_id)]: position
                for candidate_id, position in result["ranks"].items()
            }
            # Labels are recorded only for a completed ranking: a judge that
            # never returned one did not rank what it was shown.
            for label, key in label_maps[judge].items():
                labels[(judge, key)] = label
        return RankingPass(ranks, labels, len(ranking_judges))

    # ------------------------------------------------------------- outputs

    @staticmethod
    def _format_exclusions(scoring: ScoringPass) -> str:
        """One line per dropped judge, so a stored run records why."""
        return "\n".join(
            f"{judge}: {reason}" for judge, reason in scoring.excluded_judges.items()
        )

    def _persist_scores(
        self,
        run: TranslationQualityRun,
        rows: dict[Candidate, TranslationQualityCandidate],
        scoring: ScoringPass,
        ranking: RankingPass,
    ) -> None:
        """
        Write the scores.

        The run and its candidates already exist — the tasks wrote their
        content as they went — so only the ratings are new here.
        """
        run.excluded_judges = self._format_exclusions(scoring)
        run.save(update_fields=["excluded_judges"])

        TranslationQualityScore.objects.bulk_create(
            [
                TranslationQualityScore(
                    candidate=rows[key],
                    judge=judge,
                    accuracy=rating.scores["accuracy"],
                    fluency=rating.scores["fluency"],
                    terminology=rating.scores["terminology"],
                    justification=rating.justification,
                    comparative_rank=ranking.ranks.get(judge, {}).get(key),
                    comparative_label=ranking.labels.get((judge, key), ""),
                )
                for (judge, key), rating in scoring.ratings.items()
            ]
        )

    @staticmethod
    def _unchanged_display(arm: Arm) -> str:
        """Render the diagnostic, or '?' when it could not be measured."""
        return "?" if arm.unchanged_units is None else str(arm.unchanged_units)

    def _report_broken_arms(self, arms: dict[Candidate, Arm]) -> None:
        """Print why arms dropped out, so a short table is never a silent one."""
        broken = {key: arm.error for key, arm in arms.items() if arm.error}
        if not broken:
            return
        self.stdout.write(self.style.WARNING(f"\n{len(broken)} candidate(s) excluded:"))
        for key, error in sorted(broken.items(), key=lambda item: str(item[0])):
            self.stdout.write(self.style.WARNING(f"  ⊘ {key}: {error}"))

    def _report(self, rows, arms, scoring: ScoringPass, ranking: RankingPass) -> None:
        """Print the standings, the comparative pass and the verdict."""
        width = max(len(str(row.candidate)) for row in rows)
        header = (
            f"{'candidate'.ljust(width)}  mean rank  mean score  spread  "
            f"judges  unchanged"
        )
        self.stdout.write("\n" + "=" * len(header))
        self.stdout.write(header)
        self.stdout.write("-" * len(header))
        for row in rows:
            self.stdout.write(
                f"{str(row.candidate).ljust(width)}  "
                f"{row.mean_rank:9.2f}  {row.mean_score:10.2f}  "
                f"{row.spread:6.1f}  {row.judges:6d}  "
                f"{self._unchanged_display(arms[row.candidate]):>9}"
            )
        self.stdout.write(
            "\n'unchanged' counts translation units returned identical to the "
            "source. Diagnostic only — it is not part of the ranking, and some "
            "units are identical in any language."
        )

        self._report_broken_arms(arms)

        if scoring.excluded_judges:
            self.stdout.write(
                self.style.WARNING(
                    f"Judges dropped from scoring: {', '.join(scoring.excluded_judges)}"
                )
            )

        if ranking.ranks:
            self.stdout.write(
                f"\nFirst-place votes among the shortlist "
                f"({len(ranking.ranks)} of {ranking.attempted} judge(s) ranked):"
            )
            for candidate, votes in sorted(
                rank_one_votes(ranking.ranks).items(), key=lambda item: -item[1]
            ):
                self.stdout.write(f"  {candidate}: {votes}")

        winner, reason = pick_winner(
            rows, ranking.ranks, judges_attempted=ranking.attempted
        )
        self.stdout.write("")
        if winner:
            self.stdout.write(self.style.SUCCESS(f"Winner: {winner}"))
        else:
            self.stdout.write(self.style.WARNING("No clear winner."))
        self.stdout.write(f"  {reason}")
