import logging
import random
import time
from dataclasses import dataclass, field
from statistics import fmean

from celery import group
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from ol_openedx_course_translations.models import (
    TranslationBenchmark,
    TranslationBenchmarkCandidate,
    TranslationBenchmarkScore,
)
from ol_openedx_course_translations.providers.llm_providers import COMPARATIVE_LABELS
from ol_openedx_course_translations.tasks import (
    benchmark_rank_task,
    benchmark_score_task,
    benchmark_translate_task,
    benchmark_validate_task,
)
from ol_openedx_course_translations.utils.benchmark import (
    Benchmark,
    BenchmarkError,
    count_unchanged_units,
    read_benchmark,
)
from ol_openedx_course_translations.utils.constants import PROVIDER_AZURE
from ol_openedx_course_translations.utils.course_translations import (
    parse_and_validate_provider_spec,
)
from ol_openedx_course_translations.utils.quality_report import (
    SHORTLIST_CAP,
    Candidate,
    Rating,
    build_comparative_rows,
    build_rows,
    pick_comparative_winner,
    rank_one_votes,
    select_shortlist,
)

logger = logging.getLogger(__name__)

# Rough characters per token, for the pre-flight size estimate only.
CHARS_PER_TOKEN = 4

# Stage polling. The stage timeout matches translate_course's TASK_TIMEOUT: a
# 10-translator run is tens of minutes of work, so the bound is generous — it
# exists so a task lost with its worker ends the run instead of hanging it.
# Every still-pending child costs a result-backend round trip per poll —
# Celery caches a child's state only once it is ready — so a 400-task stage
# at two seconds is tens of thousands of GETs on the queue course publishing
# shares. A stage measured in tens of minutes does not need that resolution.
BENCHMARK_POLL_INTERVAL = 30
BENCHMARK_STAGE_TIMEOUT = 7200


@dataclass(frozen=True)
class Arm:
    """One candidate's content, or why it has none."""

    content: str | None = None
    error: str = ""
    # Units in this arm's content still identical to the English source.
    # Diagnostic only: some units are identical in any language, so this is
    # shown, never scored.
    unchanged_units: int = 0

    @property
    def usable(self) -> bool:
        """Whether this arm has content a judge can score."""
        return self.content is not None and not self.error


@dataclass(frozen=True)
class ScoringPass:
    """What the scoring pass produced, and which judges it lost."""

    overalls: dict[str, dict[Candidate, float]] = field(default_factory=dict)
    ratings: dict[tuple[str, Candidate], Rating] = field(default_factory=dict)
    # judge -> why it was dropped, kept so a stored run records the reason and
    # not merely the absence of its scores.
    excluded_judges: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RankingPass:
    """What the comparative pass produced, and how many judges attempted it."""

    ranks: dict[str, dict[Candidate, int]]
    labels: dict[tuple[str, Candidate], str]
    attempted: int
    # judge -> why its ranking call failed, already qualified so it reads
    # the same as a scoring exclusion. Every path that ends a run stores
    # this, because a console warning is gone by the time anyone reads the
    # standings and wonders why nothing carries a rank.
    failures: dict[str, str] = field(default_factory=dict)


class Command(BaseCommand):
    """Rate translation quality across translator/validator/judge combinations."""

    help = (
        "Translate a course block with every translator, validate each "
        "translation with every validator, and have every judge rate the results."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--benchmark-block",
            required=True,
            help=(
                "Usage key of the course block to translate, e.g. "
                "block-v1:Org+Course+Run+type@html+block@abc123. Its published "
                "body is the benchmark; nothing is bundled with the plugin."
            ),
        )
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
            "--comparative-only",
            action="store_true",
            help=(
                "Skip the per-candidate scoring pass and rank every candidate "
                "in one comparative call per judge. Cheaper and faster, but "
                "the verdict then rests on a single signal."
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
        comparative_only = options["comparative_only"]
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
            benchmark = read_benchmark(options["benchmark_block"])
        except BenchmarkError as error:
            raise CommandError(str(error)) from error

        self._confirm_run(
            translators=translators,
            judges=judges,
            benchmark=benchmark,
            skip_prompt=options["yes"],
            comparative_only=comparative_only,
        )

        run, benchmark = self._start_run(
            benchmark,
            target_language,
            translators,
            judges,
            comparative_only=comparative_only,
        )
        rows = self._create_rows(run, translators)

        failed_translators = self._translate(rows, translators, target_language, run.pk)
        self._validate(
            rows,
            translators,
            failed_translators,
            target_language,
            run.pk,
        )
        # The unvalidated rows are scaffolding: they must outlive the
        # validation stage, which reads their translation, and must not
        # outlive it by longer, or they would be scored.
        for translator in translators:
            rows.pop(Candidate(translator)).delete()
        arms = self._load_arms(run, benchmark)

        scored_rows = []
        if comparative_only:
            scoring = ScoringPass()
            contenders = sorted(
                (key for key, arm in arms.items() if arm.usable), key=str
            )
        else:
            scoring = self._score(rows, arms, judges, target_language, run.pk)
            if not scoring.overalls:
                self._report_broken_arms(arms)
                self._record_exclusions(run, scoring.excluded_judges)
                msg = f"No candidate was scored by any judge (run {run.pk})."
                raise CommandError(msg)
            scored_rows = build_rows(scoring.overalls)
            contenders = [row.candidate for row in select_shortlist(scored_rows)]

        ranking = self._rank(
            contenders,
            rows,
            judges,
            scoring.excluded_judges,
            target_language,
            run.pk,
        )
        # The verdict always comes from the comparative pass, so the standings
        # are whatever ordering the run produced: absolute positions when the
        # scoring pass ran, the comparative ranks themselves when it did not.
        comparative_rows = build_comparative_rows(ranking.ranks)
        report_rows = comparative_rows if comparative_only else scored_rows
        if not report_rows:
            self._report_broken_arms(arms)
            # _persist_scores is the usual writer and is not reached from
            # here, so this is the only chance to record why every judge's
            # ranking call failed — the case the field exists for.
            self._record_exclusions(run, scoring.excluded_judges | ranking.failures)
            # With fewer than two contenders the judges were never asked, so
            # the arms are the cause.
            msg = (
                f"Only {len(contenders)} usable candidate(s), so there was "
                f"nothing to rank (run {run.pk})."
                if len(contenders) < 2  # noqa: PLR2004
                else f"No candidate was ranked by any judge (run {run.pk})."
            )
            raise CommandError(msg)

        # Reported before the scores are written: the translations are already
        # safe on their rows, and a write failure should not also cost the
        # standings the run paid for.
        self._report(
            report_rows,
            comparative_rows,
            arms,
            scoring,
            ranking,
            comparative_only=run.comparative_only,
        )

        with transaction.atomic():
            self._persist_scores(run, rows, scoring, ranking)
            run.completed_at = timezone.now()
            run.save(update_fields=["completed_at"])
        self.stdout.write(
            f"\nStored as run {run.pk}; see the Django admin for details."
        )

    # ---------------------------------------------------------------- setup

    def _start_run(
        self, benchmark, target_language, translators, judges, *, comparative_only
    ):
        """
        Create the run row, then re-read the block it names.

        The confirmation prompt can sit for minutes and the block is live
        course content an author can publish over. Re-reading closes that
        window for the command's own copy, which feeds the unchanged-unit
        diagnostic. The tasks read for themselves, after this one and at
        best once per worker process per run, so a republish in between
        still reaches them and the diagnostic can be measured against
        different text than the arms.
        """
        run = TranslationBenchmark.objects.create(
            target_language=target_language,
            benchmark_block_id=benchmark.block_id,
            translators_arg=",".join(translators),
            judges_arg=",".join(judges),
            comparative_only=comparative_only,
        )
        return run, read_benchmark(benchmark.block_id)

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

        A provider with no ``api_key`` is skipped with a note (except Azure,
        which authenticates with an Entra token), so a partly
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
            if provider_name != PROVIDER_AZURE and not config.get("api_key"):
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
        comparative_only: bool,
    ) -> None:
        """Show the size of the run before any request is made."""
        candidates = len(translators) * len(translators)
        if comparative_only and candidates < 2:  # noqa: PLR2004
            # One translator makes one candidate, and with the scoring pass
            # skipped there is nothing else to report on it.
            msg = (
                f"Only one usable translator ({translators[0]}), so "
                "--comparative-only has nothing to compare. Pass at least two "
                "with --translators, or drop the flag to score it."
            )
            raise CommandError(msg)
        if comparative_only and candidates > len(COMPARATIVE_LABELS):
            msg = (
                f"{candidates} candidates exceed the {len(COMPARATIVE_LABELS)} "
                f"anonymous labels one comparative call can carry. Use at most "
                f"{int(len(COMPARATIVE_LABELS) ** 0.5)} translators with "
                f"--comparative-only, or drop the flag."
            )
            raise CommandError(msg)
        calls = {
            "translations": len(translators),
            "validations": candidates,
            "scoring": 0 if comparative_only else candidates * len(judges),
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
                + calls["ranking"]
                * (1 + (candidates if comparative_only else SHORTLIST_CAP))
            )
            // CHARS_PER_TOKEN
        )

        self.stdout.write(
            f"\nBenchmark:   {benchmark.display_name} ({benchmark.block_id})"
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

        ``propagate=False`` so a task that raised — because it exhausted its
        retries, or failed outside its own handler — comes back as a result to
        record rather than an exception that ends the stage: one provider
        failing must not cost the work already paid for.
        """
        if not signatures:
            return []

        self.stdout.write(f"{header}: {len(signatures)} task(s)...")
        result = group(signatures).apply_async()
        deadline = time.monotonic() + BENCHMARK_STAGE_TIMEOUT
        while not result.ready():
            if time.monotonic() > deadline:
                # A child lost with its worker never becomes ready, so without
                # a deadline here the run waits forever. Revoking stops the
                # children still queued; one already inside its LLM call runs
                # to completion, since terminating it would SIGTERM a worker
                # on a queue shared with course publishing.
                result.revoke()
                msg = (
                    f"{header} did not finish within "
                    f"{BENCHMARK_STAGE_TIMEOUT}s; remaining tasks revoked."
                )
                raise CommandError(msg)
            done = sum(1 for child in result.results if child.ready())
            self.stdout.write(f"  {done}/{len(signatures)} done\r", ending="")
            self.stdout.flush()
            time.sleep(BENCHMARK_POLL_INTERVAL)
        return result.get(timeout=BENCHMARK_STAGE_TIMEOUT, propagate=False)

    @staticmethod
    def _outcome(result) -> tuple[bool, str]:
        """
        Read a task result, treating anything unexpected as a failure.

        A block that cannot be read is named as such rather than by its
        exception class: the stage that records it can only key the reason
        by the judge or arm that hit it, so the reason itself has to say
        the fault is not theirs.
        """
        if isinstance(result, BenchmarkError):
            return False, f"benchmark unreadable: {result}"
        if not isinstance(result, dict):
            return False, f"{type(result).__name__}: {result}"
        if result.get("status") != "success":
            return False, str(result.get("error", "unknown error"))
        return True, ""

    def _create_rows(
        self, run: TranslationBenchmark, translators: list[str]
    ) -> dict[Candidate, TranslationBenchmarkCandidate]:
        """
        Create every arm up front, so tasks can address rows by id.

        The unvalidated row is created too, but only to hold the translation
        its validated arms are built from; ``handle`` deletes it
        once they exist, so it is never a candidate.
        """
        return {
            Candidate(
                translator, validator
            ): TranslationBenchmarkCandidate.objects.create(
                run=run, translator=translator, validator=validator
            )
            for translator in translators
            for validator in ["", *translators]
        }

    def _translate(
        self,
        rows: dict[Candidate, TranslationBenchmarkCandidate],
        translators: list[str],
        target_language: str,
        run_id: int,
    ) -> set[str]:
        """Translate once per translator; returns the translators that failed."""
        signatures = [
            benchmark_translate_task.s(
                rows[Candidate(translator)].pk,
                translator,
                target_language,
                run_id,
            )
            for translator in translators
        ]
        failed = set()
        results = self._dispatch(signatures, "Translating")
        for result in results:
            # A BenchmarkError escaped a task body, which only the read every
            # task makes before its own handler can do. Recorded per arm it
            # would blame whichever provider happened to hit it, durably.
            # Only here: this stage has paid for nothing, while every later
            # one holds work worth keeping and the cache is per worker per
            # run, so one cold worker is not grounds to discard the rest.
            if isinstance(result, BenchmarkError):
                raise CommandError(str(result))
        for translator, result in zip(translators, results, strict=True):
            succeeded, reason = self._outcome(result)
            if not succeeded:
                failed.add(translator)
                if not isinstance(result, dict):
                    # The task records its own failures on the row; one that
                    # died outside its handler has to be written from here,
                    # or every dependent arm reads "translation failed:"
                    # with nothing after the colon.
                    source = rows[Candidate(translator)]
                    source.error = reason
                    source.save(update_fields=["error"])
                self.stdout.write(
                    self.style.WARNING(f"⊘ translator {translator}: {reason}")
                )
        return failed

    def _validate(
        self,
        rows: dict[Candidate, TranslationBenchmarkCandidate],
        translators: list[str],
        failed_translators: set[str],
        target_language: str,
        run_id: int,
    ) -> None:
        """Review each usable translation with every validator."""
        signatures: list = []
        for translator in translators:
            if translator in failed_translators:
                # The arms of a failed translation have nothing to review. The
                # provider's own message lives on the source row, which is
                # about to be discarded, so carry it across rather than
                # leaving every arm saying only that something went wrong.
                source = rows[Candidate(translator)]
                source.refresh_from_db(fields=["error"])
                for validator in translators:
                    arm = rows[Candidate(translator, validator)]
                    arm.error = f"translation failed: {source.error}"
                    arm.save(update_fields=["error"])
                continue
            signatures.extend(
                benchmark_validate_task.s(
                    rows[Candidate(translator, validator)].pk,
                    rows[Candidate(translator)].pk,
                    validator,
                    target_language,
                    run_id,
                )
                for validator in translators
            )
        results = self._dispatch(signatures, "Validating")
        for signature, result in zip(signatures, results, strict=True):
            succeeded, reason = self._outcome(result)
            if not succeeded and not isinstance(result, dict):
                # The task records its own failures on the row; only one that
                # never reached its handler has to be written from here.
                # Updated rather than fetched: if the row is what went
                # missing, raising here would cost the run its scoring pass
                # and its report, leaving the translations stranded on rows
                # nothing has ranked.
                TranslationBenchmarkCandidate.objects.filter(
                    pk=signature.args[0], run_id=run_id
                ).update(error=reason)

    def _load_arms(
        self, run: TranslationBenchmark, benchmark: Benchmark
    ) -> dict[Candidate, Arm]:
        """
        Read back what the tasks wrote, with the diagnostic recomputed."""
        arms = {}
        for row in run.candidates.all():
            content = row.translated_content or None
            arms[Candidate(row.translator, row.validator)] = Arm(
                content=content,
                error=row.error,
                unchanged_units=(
                    count_unchanged_units(content, benchmark) if content else 0
                ),
            )
        return arms

    def _score(
        self,
        rows: dict[Candidate, TranslationBenchmarkCandidate],
        arms: dict[Candidate, Arm],
        judges: list[str],
        target_language: str,
        run_id: int,
    ) -> ScoringPass:
        """
        Have every judge score every usable candidate, one candidate per call.

        A judge that fails anywhere is dropped from the whole scoring pass, so
        every candidate ends up ranked over an identical set of judges. That is
        a decision over the whole stage, which is why the tasks return their
        ratings instead of writing them.
        """
        # Sorted, as the comparative-only branch sorts its contenders: this
        # becomes the dispatch order, and a judge that fails on more than one
        # arm keeps whichever reason arrived first. Unsorted, two identical
        # runs could store different text for the same failure.
        usable = sorted((key for key, arm in arms.items() if arm.usable), key=str)
        dispatched = [(judge, key) for judge in judges for key in usable]
        signatures = [
            benchmark_score_task.s(rows[key].pk, judge, target_language, run_id)
            for judge, key in dispatched
        ]
        results = self._dispatch(
            signatures,
            f"Scoring {len(usable)} candidate(s) against {len(judges)} judge(s)",
        )

        reasons: dict[str, str] = {}
        collected: list[tuple[str, Candidate, Rating]] = []
        for (judge, key), result in zip(dispatched, results, strict=True):
            succeeded, reason = self._outcome(result)
            if not succeeded:
                # Taken from the dispatch order, not the payload: a task that
                # died before its own handler carries no judge name, and
                # missing one here would quietly spare that judge exclusion.
                reasons.setdefault(judge, reason)
                continue
            collected.append(
                (judge, key, Rating(result["scores"], result["justification"]))
            )

        reasons = dict(sorted(reasons.items()))
        for judge, reason in reasons.items():
            self.stdout.write(self.style.WARNING(f"⊘ judge {judge} dropped: {reason}"))

        overalls: dict[str, dict[Candidate, float]] = {}
        ratings: dict[tuple[str, Candidate], Rating] = {}
        for judge, key, rating in collected:
            if judge in reasons:
                continue
            overalls.setdefault(judge, {})[key] = fmean(rating.scores.values())
            ratings[(judge, key)] = rating
        return ScoringPass(overalls, ratings, reasons)

    def _rank(  # noqa: PLR0913, PLR0917 — one parameter per stage input
        self,
        contenders: list[Candidate],
        rows: dict[Candidate, TranslationBenchmarkCandidate],
        judges: list[str],
        excluded_judges: dict[str, str],
        target_language: str,
        run_id: int,
    ) -> RankingPass:
        """
        Have each judge rank the contenders side by side, shuffled per judge.

        Shuffling per judge rather than once per run means a candidate does not
        sit in the same prompt position for everyone, so presentation order
        cannot favour it consistently. ``contenders`` is the shortlist in the
        two-pass mode and every usable candidate in comparative-only mode.
        """
        ranking_judges = [judge for judge in judges if judge not in excluded_judges]
        if len(contenders) < 2 or not ranking_judges:  # noqa: PLR2004
            return RankingPass({}, {}, 0)

        by_id = {rows[candidate].pk: candidate for candidate in contenders}
        signatures: list = []
        label_maps: dict[str, dict[str, Candidate]] = {}
        if len(contenders) > len(COMPARATIVE_LABELS):
            # Unreachable today — the shortlist is capped at SHORTLIST_CAP and
            # _confirm_run refuses a comparative-only run above the label
            # count — and kept anyway: the zip below truncates silently, so
            # what this costs if it ever fires is candidates vanishing from a
            # ranking with nothing said.
            msg = (
                f"{len(contenders)} contenders exceed the "
                f"{len(COMPARATIVE_LABELS)} anonymous labels available."
            )
            raise CommandError(msg)

        for judge in ranking_judges:
            order = list(contenders)
            random.shuffle(order)
            label_maps[judge] = dict(zip(COMPARATIVE_LABELS, order, strict=False))
            signatures.append(
                benchmark_rank_task.s(
                    judge,
                    {label: rows[key].pk for label, key in label_maps[judge].items()},
                    target_language,
                    run_id,
                )
            )

        ranks: dict[str, dict[Candidate, int]] = {}
        labels: dict[tuple[str, Candidate], str] = {}
        failures: dict[str, str] = {}
        dispatched = self._dispatch(
            signatures, f"Ranking {len(contenders)} candidate(s)"
        )
        for judge, result in zip(ranking_judges, dispatched, strict=True):
            succeeded, reason = self._outcome(result)
            if not succeeded:
                self.stdout.write(
                    self.style.WARNING(f"⊘ judge {judge} ranking failed: {reason}")
                )
                # Qualified here so the stored line says which pass it
                # came from, and so this map is interchangeable with the
                # scoring pass's.
                failures[judge] = f"ranking: {reason}"
                continue
            ranks[judge] = {
                by_id[int(candidate_id)]: position
                for candidate_id, position in result["ranks"].items()
            }
            # Labels are recorded only for a completed ranking: a judge that
            # never returned one did not rank what it was shown.
            for label, key in label_maps[judge].items():
                labels[(judge, key)] = label
        return RankingPass(ranks, labels, len(ranking_judges), failures)

    # ------------------------------------------------------------- outputs

    @staticmethod
    def _record_exclusions(run: TranslationBenchmark, reasons: dict[str, str]) -> None:
        """
        Store one line per judge that dropped out, so a run records why.

        Sorted here, not by the passes that produce the maps: a union of two
        sorted dicts is not itself sorted. Called from every path that ends a
        run, because the ones that raise never reach ``_persist_scores``.
        """
        run.excluded_judges = "\n".join(
            f"{judge}: {reason}" for judge, reason in sorted(reasons.items())
        )
        run.save(update_fields=["excluded_judges"])

    def _persist_scores(
        self,
        run: TranslationBenchmark,
        rows: dict[Candidate, TranslationBenchmarkCandidate],
        scoring: ScoringPass,
        ranking: RankingPass,
    ) -> None:
        """
        Write the scores.

        The run and its candidates already exist — the tasks wrote their
        content as they went — so only the ratings and the judge exclusions
        are new here.

        A comparative-only run has no ratings at all, so the rows it writes
        come from the ranking instead and leave the three criteria null.
        Either way one row per (candidate, judge) is what the admin reads.
        """
        self._record_exclusions(run, scoring.excluded_judges | ranking.failures)

        judged = set(scoring.ratings) | {
            (judge, key) for judge, ranks in ranking.ranks.items() for key in ranks
        }
        scores = []
        for judge, key in sorted(judged, key=lambda pair: (pair[0], str(pair[1]))):
            rating = scoring.ratings.get((judge, key))
            scores.append(
                TranslationBenchmarkScore(
                    candidate=rows[key],
                    judge=judge,
                    accuracy=rating.scores["accuracy"] if rating else None,
                    fluency=rating.scores["fluency"] if rating else None,
                    terminology=rating.scores["terminology"] if rating else None,
                    justification=rating.justification if rating else "",
                    comparative_rank=ranking.ranks.get(judge, {}).get(key),
                    comparative_label=ranking.labels.get((judge, key), ""),
                )
            )
        TranslationBenchmarkScore.objects.bulk_create(scores)

    def _report_broken_arms(self, arms: dict[Candidate, Arm]) -> None:
        """Print why arms dropped out, so a short table is never a silent one."""
        broken = {
            key: arm.error or "no content and no recorded error"
            for key, arm in arms.items()
            if not arm.usable
        }
        if not broken:
            return
        self.stdout.write(self.style.WARNING(f"\n{len(broken)} candidate(s) excluded:"))
        for key, error in sorted(broken.items(), key=lambda item: str(item[0])):
            self.stdout.write(self.style.WARNING(f"  ⊘ {key}: {error}"))

    def _report(  # noqa: PLR0913 — one parameter per section printed
        self,
        rows,
        comparative_rows,
        arms,
        scoring: ScoringPass,
        ranking: RankingPass,
        *,
        comparative_only: bool,
    ) -> None:
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
                f"{row.mean_rank:9.2f}  "
                f"{'—' if row.mean_score is None else f'{row.mean_score:.2f}':>10}  "
                f"{row.spread:6.1f}  {row.judges:6d}  "
                f"{arms[row.candidate].unchanged_units:>9}"
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

        # The run's own record of which passes it ran, rather than a guess
        # from whether any row happens to carry a score.
        if comparative_only:
            self.stdout.write(
                "\nRanks come from the comparative pass alone: the scoring "
                "pass was skipped, so 'mean rank' is the mean comparative rank "
                "and there is no mean score."
            )

        # Printed whenever the pass ran, even if every judge failed: the
        # count is what separates "all of them failed" from "some did", and
        # the verdict line collapses both into "no candidates were ranked".
        # Skipped when nothing was dispatched, so a run with fewer than two
        # contenders says that instead of advertising a pass it never made.
        if ranking.attempted:
            self.stdout.write(
                f"\nFirst-place votes among the contenders "
                f"({len(ranking.ranks)} of {ranking.attempted} judge(s) ranked):"
            )
            votes_by_candidate = sorted(
                rank_one_votes(ranking.ranks).items(), key=lambda item: -item[1]
            )
            for candidate, votes in votes_by_candidate:
                self.stdout.write(f"  {candidate}: {votes}")
            if not votes_by_candidate:
                # No judge returned a ranking at all, or every one that did
                # tied at the top or named no rank 1.
                self.stdout.write("  no judge named a single best candidate")
        else:
            self.stdout.write("\nComparative pass skipped: fewer than two contenders.")

        winner, reason = pick_comparative_winner(comparative_rows)
        self.stdout.write("")
        if winner:
            self.stdout.write(self.style.SUCCESS(f"Winner: {winner}"))
        else:
            self.stdout.write(self.style.WARNING("No clear winner."))
        self.stdout.write(f"  {reason}")
