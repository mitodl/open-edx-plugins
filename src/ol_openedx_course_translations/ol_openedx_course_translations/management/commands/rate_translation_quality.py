"""
Benchmark translation quality across LLM providers.

Translates one fixed benchmark unit with every translator, edits each
translation with every validator, has every judge score the results, and
reports which configuration wins. See
``docs/adr/0001-translation-quality-benchmark-methodology.md`` for why the
judging works the way it does.
"""

import logging
import random
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

import ol_openedx_course_translations
from ol_openedx_course_translations.models import (
    TranslationQualityCandidate,
    TranslationQualityRun,
    TranslationQualityScore,
)
from ol_openedx_course_translations.providers.llm_providers import COMPARATIVE_LABELS
from ol_openedx_course_translations.utils.constants import ENGLISH_LANGUAGE_CODE
from ol_openedx_course_translations.utils.course_translations import (
    HtmlXmlTranslationHelper,
    get_translation_provider,
    looks_like_markup,
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

BENCHMARK_PATH = (
    Path(ol_openedx_course_translations.__file__).parent
    / "benchmarks"
    / "benchmark_course_content.xml"
)

# Rough characters per token, for the pre-flight size estimate only.
CHARS_PER_TOKEN = 4


@dataclass(frozen=True)
class Benchmark:
    """The benchmark content, read and parsed once per run."""

    content: str
    # Stripped source unit texts, for the unchanged-unit diagnostic.
    units: frozenset[str]
    elements: int


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
    excluded_judges: tuple[str, ...]


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

        benchmark = self._read_benchmark()
        self._confirm_run(
            translators=translators,
            judges=judges,
            benchmark=benchmark,
            skip_prompt=options["yes"],
        )

        translations = self._translate(translators, target_language, benchmark)
        arms = self._validate(translators, translations, target_language, benchmark)
        scoring = self._score(arms, judges, target_language, benchmark)
        if not scoring.overalls:
            self._report_broken_arms(arms)
            msg = "No candidate was scored by any judge."
            raise CommandError(msg)

        rows = build_rows(scoring.overalls)
        shortlist = select_shortlist(rows)
        ranking = self._rank(
            shortlist, arms, judges, scoring.excluded_judges, target_language, benchmark
        )

        # Reported before persisting: the run costs real money, and a write
        # failure should not also throw away the result it paid for.
        self._report(rows, arms, scoring, ranking)

        with transaction.atomic():
            run = self._persist(
                target_language=target_language,
                translators=translators,
                judges=judges,
                arms=arms,
                scoring=scoring,
                ranking=ranking,
            )
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

    def _read_benchmark(self) -> Benchmark:
        """
        Read and parse the benchmark before anything is spent.

        Parsing here means a malformed fixture is reported as the cause,
        rather than surfacing later as every translator appearing to fail.
        """
        if not BENCHMARK_PATH.exists():
            msg = f"Benchmark file is missing: {BENCHMARK_PATH}"
            raise CommandError(msg)
        content = BENCHMARK_PATH.read_text(encoding="utf-8")
        if not content.strip():
            msg = f"Benchmark file is empty: {BENCHMARK_PATH}"
            raise CommandError(msg)
        try:
            units, elements = self._units_and_elements(content)
        except Exception as error:
            msg = f"Benchmark file is not well-formed XML ({BENCHMARK_PATH}): {error}"
            raise CommandError(msg) from error
        return Benchmark(
            content=content,
            units=frozenset(unit.strip() for unit in units),
            elements=elements,
        )

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

    def _run_lanes(self, jobs: list[tuple[str, Any, Callable[[], Any]]]) -> dict:
        """
        Run jobs concurrently, one lane per provider.

        Jobs sharing a provider run in sequence, so a run cannot rate-limit
        itself against a single API key; different providers run in parallel.
        Each result is ``{"value": ..., "error": str | None}``.
        """
        if not jobs:
            return {}

        lanes: dict[str, list[tuple[Any, Callable[[], Any]]]] = {}
        for spec, key, work in jobs:
            lanes.setdefault(spec.split("/", 1)[0], []).append((key, work))

        def run_lane(lane):
            results = []
            for key, work in lane:
                try:
                    results.append((key, {"value": work(), "error": None}))
                except Exception as error:
                    # Logged with a traceback because this catches genuine bugs
                    # as well as provider failures, and the two read alike in
                    # the summary line.
                    logger.exception("job %s failed", key)
                    results.append(
                        (
                            key,
                            {
                                "value": None,
                                "error": f"{type(error).__name__}: {error}",
                            },
                        )
                    )
            return results

        collected: dict[Any, Any] = {}
        with ThreadPoolExecutor(max_workers=len(lanes)) as pool:
            for lane_results in pool.map(run_lane, lanes.values()):
                collected.update(lane_results)
        return collected

    def _provider_for(self, spec: str):
        provider_name, model_name = spec.split("/", 1)
        return get_translation_provider(provider_name, model_name)

    @staticmethod
    def _units_and_elements(markup: str) -> tuple[list[str], int]:
        """Extract translatable units and count elements, for the arm checks."""
        helper = HtmlXmlTranslationHelper(is_xml=True)
        root, units, _ = helper.extract_units(markup)
        # Comments and processing instructions have non-string tags; counting
        # them would make a validator that touches a comment look like one that
        # restructured the document.
        return units, sum(1 for node in root.iter() if isinstance(node.tag, str))

    def _unchanged_units(self, markup: str, benchmark: Benchmark) -> int | None:
        """
        Count units whose text still matches some source unit.

        Diagnostic only, so a parse failure returns None rather than
        discarding an arm whose content is otherwise scoreable.
        """
        try:
            units, _ = self._units_and_elements(markup)
        except Exception:
            logger.warning("could not measure unchanged units", exc_info=True)
            return None
        return sum(1 for unit in units if unit.strip() in benchmark.units)

    def _translate(
        self, translators: list[str], target_language: str, benchmark: Benchmark
    ) -> dict[str, dict]:
        """Translate the benchmark once per translator; arms reuse the result."""
        self.stdout.write(f"Translating with {len(translators)} translator(s)...")

        def translate(spec):
            def work():
                translated = self._provider_for(spec).translate_text(
                    benchmark.content, target_language, tag_handling="xml"
                )
                # translate_text swallows failures and hands back the source,
                # so an unchanged document means the translation did not happen.
                if not translated or translated.strip() == benchmark.content.strip():
                    msg = "provider returned the source unchanged"
                    raise RuntimeError(msg)
                try:
                    _, elements = self._units_and_elements(translated)
                except Exception as error:
                    msg = f"translation does not parse as XML: {error}"
                    raise RuntimeError(msg) from error
                # A partial translation is not identical to the source, so the
                # check above cannot see it: units the model skipped come back
                # in English. Counted here and shown in the report.
                return Arm(
                    content=translated,
                    elements=elements,
                    unchanged_units=self._unchanged_units(translated, benchmark),
                )

            return work

        return self._run_lanes([(spec, spec, translate(spec)) for spec in translators])

    def _validate(
        self,
        translators: list[str],
        translations: dict[str, dict],
        target_language: str,
        benchmark: Benchmark,
    ) -> dict[Candidate, Arm]:
        """Build every (translator, validator) arm, including the unvalidated one."""
        arms: dict[Candidate, Arm] = {}
        jobs: list[tuple[str, Any, Callable[[], Any]]] = []

        for translator in translators:
            translated = translations[translator]
            if translated["error"]:
                for validator in ["", *translators]:
                    arms[Candidate(translator, validator)] = Arm(
                        error=f"translation failed: {translated['error']}"
                    )
                continue

            arm = translated["value"]
            arms[Candidate(translator)] = arm
            jobs.extend(
                (
                    validator,
                    Candidate(translator, validator),
                    self._validation_job(validator, arm, target_language, benchmark),
                )
                for validator in translators
            )

        if jobs:
            self.stdout.write(f"Validating {len(jobs)} arm(s)...")
            for key, result in self._run_lanes(jobs).items():
                arms[key] = (
                    Arm(error=result["error"]) if result["error"] else result["value"]
                )
        return arms

    def _validation_job(
        self,
        validator: str,
        translated: Arm,
        target_language: str,
        benchmark: Benchmark,
    ) -> Callable[[], Arm]:
        def work():
            reviewed = self._provider_for(validator).validate_translation(
                source_language=ENGLISH_LANGUAGE_CODE,
                target_language=target_language,
                source_content=benchmark.content,
                translated_content=translated.content,
            )
            # Validation sends whole markup and bypasses the DOM-aware path, so
            # it can return prose or restructured markup. Production applies the
            # same looks_like_markup gate (tasks.py) but falls back to the
            # unvalidated translation; here the arm is dropped instead, so
            # nothing unusable is scored. The element-count check below has no
            # production counterpart — it is benchmark-only.
            if not looks_like_markup(reviewed):
                msg = "validator returned no markup"
                raise RuntimeError(msg)
            try:
                _, after_elements = self._units_and_elements(reviewed)
            except Exception as error:
                msg = f"validator returned markup that does not parse: {error}"
                raise RuntimeError(msg) from error
            # Compared against the count taken when the translation was made,
            # so a translator-side problem is never blamed on the validator.
            if after_elements != translated.elements:
                msg = (
                    f"validator changed the markup structure "
                    f"({translated.elements} elements in, {after_elements} out)"
                )
                raise RuntimeError(msg)
            return Arm(
                content=reviewed,
                elements=after_elements,
                unchanged_units=self._unchanged_units(reviewed, benchmark),
            )

        return work

    def _score(
        self,
        arms: dict[Candidate, Arm],
        judges: list[str],
        target_language: str,
        benchmark: Benchmark,
    ) -> ScoringPass:
        """
        Have every judge score every usable candidate, one candidate per call.

        A judge that fails anywhere is dropped from the whole scoring pass, so
        every candidate ends up ranked over an identical set of judges.
        """
        usable = {key: arm for key, arm in arms.items() if arm.usable}
        jobs = [
            (
                judge,
                (judge, key),
                self._scoring_job(judge, arm, target_language, benchmark),
            )
            for judge in judges
            for key, arm in usable.items()
        ]
        self.stdout.write(
            f"Scoring {len(usable)} candidate(s) with {len(judges)} judge(s)..."
        )
        results = self._run_lanes(jobs)

        reasons: dict[str, str] = {}
        for (judge, key), result in results.items():
            if result["error"] and judge not in reasons:
                reasons[judge] = f"{key} → {result['error']}"
        for judge, reason in sorted(reasons.items()):
            self.stdout.write(self.style.WARNING(f"⊘ judge {judge} dropped: {reason}"))

        overalls: dict[str, dict[Candidate, float]] = {}
        ratings: dict[tuple[str, Candidate], Rating] = {}
        for (judge, key), result in results.items():
            if judge in reasons:
                continue
            rating = result["value"]
            overalls.setdefault(judge, {})[key] = average_overall(rating.scores)
            ratings[(judge, key)] = rating
        return ScoringPass(overalls, ratings, tuple(sorted(reasons)))

    def _scoring_job(
        self, judge: str, arm: Arm, target_language: str, benchmark: Benchmark
    ) -> Callable[[], Rating]:
        def work():
            return self._provider_for(judge).rate_translation(
                source_language=ENGLISH_LANGUAGE_CODE,
                target_language=target_language,
                source_content=benchmark.content,
                translated_content=arm.content,
            )

        return work

    def _rank(  # noqa: PLR0913, PLR0917
        self,
        shortlist,
        arms: dict[Candidate, Arm],
        judges: list[str],
        excluded_judges: tuple[str, ...],
        target_language: str,
        benchmark: Benchmark,
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

        self.stdout.write(
            f"Ranking the top {len(shortlist)} with {len(ranking_judges)} judge(s)..."
        )
        jobs = []
        label_maps: dict[str, dict[str, Candidate]] = {}
        for judge in ranking_judges:
            order = [row.candidate for row in shortlist]
            random.shuffle(order)
            label_maps[judge] = dict(zip(COMPARATIVE_LABELS, order, strict=False))
            jobs.append(
                (
                    judge,
                    judge,
                    self._ranking_job(
                        judge, label_maps[judge], arms, target_language, benchmark
                    ),
                )
            )

        ranks: dict[str, dict[Candidate, int]] = {}
        labels: dict[tuple[str, Candidate], str] = {}
        for judge, result in self._run_lanes(jobs).items():
            if result["error"]:
                self.stdout.write(
                    self.style.WARNING(
                        f"⊘ judge {judge} ranking failed: {result['error']}"
                    )
                )
                continue
            ranks[judge] = result["value"]
            # Labels are recorded only for a completed ranking: a judge that
            # never returned one did not rank what it was shown.
            for label, key in label_maps[judge].items():
                labels[(judge, key)] = label
        return RankingPass(ranks, labels, len(ranking_judges))

    def _ranking_job(
        self,
        judge: str,
        label_map: dict[str, Candidate],
        arms: dict[Candidate, Arm],
        target_language: str,
        benchmark: Benchmark,
    ) -> Callable[[], dict]:
        def work():
            # Built inside the job so that a candidate missing its content —
            # a bug, since everything shortlisted was scored — costs this
            # judge's ranking rather than the whole run's report.
            payload = {}
            for label, key in label_map.items():
                content = arms[key].content
                if content is None:
                    msg = f"shortlisted candidate {key} has no content"
                    raise RuntimeError(msg)
                payload[label] = content

            ranks = self._provider_for(judge).rank_translations(
                source_language=ENGLISH_LANGUAGE_CODE,
                target_language=target_language,
                source_content=benchmark.content,
                candidates=payload,
            )
            return {label_map[label]: position for label, position in ranks.items()}

        return work

    # ------------------------------------------------------------- outputs

    def _persist(  # noqa: PLR0913
        self,
        *,
        target_language: str,
        translators: list[str],
        judges: list[str],
        arms: dict[Candidate, Arm],
        scoring: ScoringPass,
        ranking: RankingPass,
    ) -> TranslationQualityRun:
        run = TranslationQualityRun.objects.create(
            target_language=target_language,
            benchmark_fixture=BENCHMARK_PATH.name,
            translators_arg=",".join(translators),
            judges_arg=",".join(judges),
        )

        # bulk_create does not populate primary keys on MySQL, and the scores
        # need them, so candidates are created one at a time.
        rows = {
            key: TranslationQualityCandidate.objects.create(
                run=run,
                translator=key.translator,
                validator=key.validator,
                error=arm.error,
            )
            for key, arm in arms.items()
        }

        scores = [
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
        TranslationQualityScore.objects.bulk_create(scores)
        return run

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
        self.stdout.write("\n" + "=" * (width + 54))
        self.stdout.write(
            f"{'candidate'.ljust(width)}  mean rank  mean score  spread  "
            f"judges  unchanged"
        )
        self.stdout.write("-" * (width + 54))
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
