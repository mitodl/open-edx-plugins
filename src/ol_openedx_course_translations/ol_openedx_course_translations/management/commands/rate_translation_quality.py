"""
Benchmark translation quality across LLM providers.

Translates one fixed benchmark unit with every translator, edits each
translation with every validator (and keeps an unvalidated arm), has every
judge score the results, and reports which configuration wins. See
``docs/adr/0001-translation-quality-benchmark-methodology.md`` for why the
judging works the way it does.
"""

import random
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
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
from ol_openedx_course_translations.providers.llm_providers import (
    COMPARATIVE_LABELS,
)
from ol_openedx_course_translations.utils.constants import ENGLISH_LANGUAGE_CODE
from ol_openedx_course_translations.utils.course_translations import (
    get_translation_provider,
    looks_like_markup,
    parse_and_validate_provider_spec,
)
from ol_openedx_course_translations.utils.quality_report import (
    average_overall,
    build_rows,
    pick_winner,
    rank_one_votes,
    select_shortlist,
)

BENCHMARK_PATH = (
    Path(ol_openedx_course_translations.__file__).parent
    / "benchmarks"
    / "benchmark_course_content.xml"
)

# Rough characters per token, for the pre-flight spend estimate only.
CHARS_PER_TOKEN = 4

NO_VALIDATOR = ""


class Command(BaseCommand):
    """Rate translation quality across translator/validator/judge combinations."""

    help = (
        "Translate a fixed benchmark unit with every translator, validate each "
        "translation with every validator, and have every judge rate the results."
    )

    def add_arguments(self, parser):
        """Add command arguments."""
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
            help="Skip the spend confirmation prompt.",
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

        source_content = self._read_benchmark()
        self._confirm_spend(
            translators=translators,
            judges=judges,
            source_content=source_content,
            skip_prompt=options["yes"],
        )

        translations = self._translate(translators, target_language, source_content)
        candidates = self._validate(
            translators, translations, target_language, source_content
        )
        scored, excluded_judges = self._score(
            candidates, judges, target_language, source_content
        )
        if not scored:
            msg = "No candidate was scored by any judge."
            raise CommandError(msg)

        rows = build_rows(scored)
        shortlist = select_shortlist(rows)
        comparative = self._rank(
            shortlist,
            candidates,
            judges,
            excluded_judges,
            target_language,
            source_content,
        )

        with transaction.atomic():
            run = self._persist(
                target_language=target_language,
                translators=translators,
                judges=judges,
                candidates=candidates,
                scored=scored,
                comparative=comparative,
            )

        self._report(rows, comparative, excluded_judges, run)

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

        An entry whose provider has no api_key is skipped with a note rather
        than failing the run, so a partly configured environment still produces
        a usable comparison.
        """
        requested = [entry.strip() for entry in raw.split(",") if entry.strip()]
        if not requested:
            requested = [
                name
                for name, config in settings.TRANSLATIONS_PROVIDERS.items()
                if isinstance(config, dict)
            ]

        resolved = []
        for entry in requested:
            try:
                provider_name, model_name = parse_and_validate_provider_spec(entry)
            except CommandError as error:
                self.stdout.write(
                    self.style.WARNING(f"⊘ skipped {role} {entry}: {error}")
                )
                continue
            resolved.append(f"{provider_name}/{model_name}")
        # 'openai' and 'openai/<default_model>' resolve to the same spec, and a
        # repeat would collide on the per-run unique constraint.
        return list(dict.fromkeys(resolved))

    def _read_benchmark(self) -> str:
        if not BENCHMARK_PATH.exists():
            msg = f"Benchmark file is missing: {BENCHMARK_PATH}"
            raise CommandError(msg)
        source_content = BENCHMARK_PATH.read_text(encoding="utf-8")
        if not source_content.strip():
            msg = f"Benchmark file is empty: {BENCHMARK_PATH}"
            raise CommandError(msg)
        return source_content

    def _confirm_spend(
        self,
        *,
        translators: list[str],
        judges: list[str],
        source_content: str,
        skip_prompt: bool,
    ) -> None:
        """Show what the run will cost before any request is made."""
        candidates = len(translators) * (len(translators) + 1)
        calls = {
            "translations": len(translators),
            "validations": len(translators) * len(translators),
            "scoring": candidates * len(judges),
            "ranking": len(judges),
        }
        total_calls = sum(calls.values())
        # Every call carries the source; scoring and ranking carry candidates too.
        payload_chars = len(source_content)
        approx_tokens = (
            payload_chars * (total_calls + calls["scoring"] + calls["ranking"] * 4)
        ) // CHARS_PER_TOKEN

        self.stdout.write(
            f"\nBenchmark:   {BENCHMARK_PATH.name}"
            f"\nTranslators: {', '.join(translators)}"
            f"\nJudges:      {', '.join(judges)}"
            f"\nCandidates:  {candidates}"
            f"\nLLM calls:   ~{total_calls} "
            f"({calls['translations']} translate, {calls['validations']} validate, "
            f"{calls['scoring']} score, {calls['ranking']} rank)"
            f"\nInput tokens: ~{approx_tokens:,} (rough estimate)\n"
        )
        if skip_prompt:
            return
        answer = input("Proceed? y/n: ").strip().lower()
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
                except Exception as error:  # noqa: BLE001
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

    def _translate(
        self, translators: list[str], target_language: str, source_content: str
    ) -> dict[str, dict]:
        """Translate the benchmark once per translator; arms reuse the result."""
        self.stdout.write(f"Translating with {len(translators)} translator(s)...")

        def translate(spec):
            def work():
                translated = self._provider_for(spec).translate_text(
                    source_content, target_language, tag_handling="xml"
                )
                # translate_text swallows failures and hands back the source,
                # so an unchanged document means the translation did not happen.
                if not translated or translated.strip() == source_content.strip():
                    msg = "provider returned the source unchanged"
                    raise RuntimeError(msg)
                return translated

            return work

        return self._run_lanes([(spec, spec, translate(spec)) for spec in translators])

    def _validate(
        self,
        translators: list[str],
        translations: dict[str, dict],
        target_language: str,
        source_content: str,
    ) -> dict[tuple[str, str], dict]:
        """Build every (translator, validator) arm, including the unvalidated one."""
        candidates: dict[tuple[str, str], dict] = {}
        jobs: list[tuple[str, Any, Callable[[], Any]]] = []

        for translator in translators:
            translated = translations[translator]
            if translated["error"]:
                for validator in [NO_VALIDATOR, *translators]:
                    candidates[(translator, validator)] = {
                        "content": None,
                        "error": f"translation failed: {translated['error']}",
                    }
                continue

            candidates[(translator, NO_VALIDATOR)] = {
                "content": translated["value"],
                "error": "",
            }
            jobs.extend(
                (
                    validator,
                    (translator, validator),
                    self._validation_job(
                        validator,
                        translated["value"],
                        target_language,
                        source_content,
                    ),
                )
                for validator in translators
            )

        if jobs:
            self.stdout.write(f"Validating {len(jobs)} arm(s)...")
            for key, result in self._run_lanes(jobs).items():
                candidates[key] = {
                    "content": result["value"],
                    "error": result["error"] or "",
                }
        return candidates

    def _validation_job(
        self,
        validator: str,
        translated: str,
        target_language: str,
        source_content: str,
    ) -> Callable[[], str]:
        def work():
            reviewed = self._provider_for(validator).validate_translation(
                source_language=ENGLISH_LANGUAGE_CODE,
                target_language=target_language,
                source_content=source_content,
                translated_content=translated,
            )
            # Validation sends whole markup and bypasses the DOM-aware path, so
            # it can return prose or mangled tags; production rejects the same way.
            if not looks_like_markup(reviewed):
                msg = "validator returned unusable output"
                raise RuntimeError(msg)
            return reviewed

        return work

    def _score(
        self,
        candidates: dict[tuple[str, str], dict],
        judges: list[str],
        target_language: str,
        source_content: str,
    ) -> tuple[dict[str, dict], list[str]]:
        """
        Have every judge score every usable candidate, one candidate per call.

        A judge that fails anywhere is dropped from the whole run, so every
        candidate ends up ranked over an identical set of judges.
        """
        usable = {key: value for key, value in candidates.items() if not value["error"]}
        jobs = [
            (
                judge,
                (judge, key),
                self._scoring_job(
                    judge, value["content"], target_language, source_content
                ),
            )
            for judge in judges
            for key, value in usable.items()
        ]
        self.stdout.write(
            f"Scoring {len(usable)} candidate(s) with {len(judges)} judge(s)..."
        )
        results = self._run_lanes(jobs)

        failed = {
            judge
            for (judge, _), result in results.items()
            if result["error"] or result["value"]["error"]
        }
        for judge in sorted(failed):
            self.stdout.write(
                self.style.WARNING(f"⊘ judge {judge} dropped: it failed on a candidate")
            )

        overalls: dict[str, dict] = {}
        self._justifications: dict[tuple[str, tuple[str, str]], str] = {}
        self._scores: dict[tuple[str, tuple[str, str]], dict] = {}
        for (judge, key), result in results.items():
            if judge in failed:
                continue
            rating = result["value"]
            overalls.setdefault(judge, {})[key] = average_overall(rating["scores"])
            self._scores[(judge, key)] = rating["scores"]
            self._justifications[(judge, key)] = rating["justification"]
        return overalls, sorted(failed)

    def _scoring_job(
        self, judge: str, content: str, target_language: str, source_content: str
    ) -> Callable[[], dict]:
        def work():
            return self._provider_for(judge).rate_translation(
                source_language=ENGLISH_LANGUAGE_CODE,
                target_language=target_language,
                source_content=source_content,
                translated_content=content,
            )

        return work

    def _rank(  # noqa: PLR0913, PLR0917
        self,
        shortlist,
        candidates: dict[tuple[str, str], dict],
        judges: list[str],
        excluded_judges: list[str],
        target_language: str,
        source_content: str,
    ) -> dict[str, dict]:
        """
        Have each judge rank the shortlist side by side, shuffled per judge.

        Shuffling per judge rather than once per run means a candidate does not
        sit in the same prompt position for everyone, so presentation order
        cannot favour it consistently.
        """
        self._labels: dict[tuple[str, tuple[str, str]], str] = {}
        ranking_judges = [judge for judge in judges if judge not in excluded_judges]
        if len(shortlist) < 2 or not ranking_judges:  # noqa: PLR2004
            return {}

        self.stdout.write(
            f"Ranking the top {len(shortlist)} with {len(ranking_judges)} judge(s)..."
        )
        jobs = []
        for judge in ranking_judges:
            order = [row.candidate for row in shortlist]
            random.shuffle(order)
            label_map = dict(zip(COMPARATIVE_LABELS, order, strict=False))
            for label, key in label_map.items():
                self._labels[(judge, key)] = label
            jobs.append(
                (
                    judge,
                    judge,
                    self._ranking_job(
                        judge,
                        {
                            label: candidates[key]["content"]
                            for label, key in label_map.items()
                        },
                        label_map,
                        target_language,
                        source_content,
                    ),
                )
            )

        ranked = {}
        for judge, result in self._run_lanes(jobs).items():
            if result["error"]:
                self.stdout.write(
                    self.style.WARNING(
                        f"⊘ judge {judge} ranking failed: {result['error']}"
                    )
                )
                continue
            if result["value"]:
                ranked[judge] = result["value"]
        return ranked

    def _ranking_job(
        self,
        judge: str,
        payload: dict[str, str],
        label_map: dict[str, tuple[str, str]],
        target_language: str,
        source_content: str,
    ) -> Callable[[], dict]:
        def work():
            result = self._provider_for(judge).rank_translations(
                source_language=ENGLISH_LANGUAGE_CODE,
                target_language=target_language,
                source_content=source_content,
                candidates=payload,
            )
            if result["error"]:
                # Surface it as a failure so the run says the judge dropped out
                # of the comparative pass instead of quietly omitting its votes.
                msg = f"ranking rejected: {result['error']}"
                raise RuntimeError(msg)
            return {
                label_map[label]: position
                for label, position in result["ranks"].items()
            }

        return work

    # ------------------------------------------------------------- outputs

    def _persist(  # noqa: PLR0913
        self,
        *,
        target_language: str,
        translators: list[str],
        judges: list[str],
        candidates: dict[tuple[str, str], dict],
        scored: dict[str, dict],
        comparative: dict[str, dict],
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
                translator=key[0],
                validator=key[1],
                error=value["error"],
            )
            for key, value in candidates.items()
        }

        scores = [
            TranslationQualityScore(
                candidate=rows[key],
                judge=judge,
                accuracy=self._scores[(judge, key)]["accuracy"],
                fluency=self._scores[(judge, key)]["fluency"],
                terminology=self._scores[(judge, key)]["terminology"],
                justification=self._justifications[(judge, key)],
                comparative_rank=comparative.get(judge, {}).get(key),
                comparative_label=self._labels.get((judge, key), ""),
            )
            for judge, overalls in scored.items()
            for key in overalls
        ]
        TranslationQualityScore.objects.bulk_create(scores)
        return run

    def _report(self, rows, comparative, excluded_judges, run) -> None:
        """Print the standings, the comparative pass and the verdict."""
        width = max(len(self._label(row.candidate)) for row in rows)
        self.stdout.write("\n" + "=" * (width + 44))
        self.stdout.write(
            f"{'candidate'.ljust(width)}  mean rank  mean score  spread  judges"
        )
        self.stdout.write("-" * (width + 44))
        for row in rows:
            self.stdout.write(
                f"{self._label(row.candidate).ljust(width)}  "
                f"{row.mean_rank:9.2f}  {row.mean_score:10.2f}  "
                f"{row.spread:6.1f}  {row.judges:6d}"
            )

        if excluded_judges:
            self.stdout.write(
                self.style.WARNING(
                    f"\nJudges dropped from this run: {', '.join(excluded_judges)}"
                )
            )

        if comparative:
            self.stdout.write(
                f"\nFirst-place votes among the shortlist "
                f"({len(comparative)} judge(s) ranked):"
            )
            for candidate, votes in sorted(
                rank_one_votes(comparative).items(), key=lambda item: -item[1]
            ):
                self.stdout.write(f"  {self._label(candidate)}: {votes}")

        winner, reason = pick_winner(rows, comparative)
        self.stdout.write("")
        if winner:
            self.stdout.write(self.style.SUCCESS(f"Winner: {self._label(winner)}"))
        else:
            self.stdout.write(self.style.WARNING("No clear winner."))
        self.stdout.write(f"  {reason}")
        self.stdout.write(
            f"\nStored as run {run.pk}; see the Django admin for details."
        )

    def _label(self, candidate: tuple[str, str]) -> str:
        translator, validator = candidate
        return f"{translator} → {validator or 'none'}"
