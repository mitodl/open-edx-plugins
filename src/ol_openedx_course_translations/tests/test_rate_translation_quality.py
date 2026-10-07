"""
Tests for the translation quality benchmark.

Three layers: how a judge's reply is parsed, how scores become an ordering,
and whether the command joins those together and stores the result. The
command tests lean on a scripted provider whose output identifies which
translator produced it, so a mis-joined label or candidate fails loudly
instead of producing a plausible leaderboard.
"""

import itertools
import random
import re
from io import StringIO
from pathlib import Path
from statistics import fmean
from typing import ClassVar
from unittest import mock

import pytest
from celery import current_app
from django.contrib import admin
from django.contrib.auth import get_permission_codename
from django.core.management import call_command
from django.core.management.base import CommandError
from litellm import BadRequestError, RateLimitError, Timeout
from ol_openedx_course_translations.admin import (
    TranslationQualityCandidateInline,
    TranslationQualityRunAdmin,
)
from ol_openedx_course_translations.management.commands import (
    rate_translation_quality as benchmark_command,
)
from ol_openedx_course_translations.models import (
    TranslationQualityCandidate,
    TranslationQualityRun,
    TranslationQualityScore,
)
from ol_openedx_course_translations.providers import llm_providers
from ol_openedx_course_translations.providers.llm_providers import (
    AnthropicProvider,
    OpenAIProvider,
)
from ol_openedx_course_translations.utils import benchmark as benchmark_module
from ol_openedx_course_translations.utils.benchmark import (
    BENCHMARK_TAG_HANDLING,
    Benchmark,
    BenchmarkError,
    units_and_elements,
)
from ol_openedx_course_translations.utils.course_translations import (
    HtmlXmlTranslationHelper,
    looks_like_markup,
)
from ol_openedx_course_translations.utils.quality_report import (
    SHORTLIST_CAP,
    Candidate,
    CandidateRow,
    Rating,
    build_comparative_rows,
    build_rows,
    pick_comparative_winner,
    rank_one_votes,
    select_shortlist,
)
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.exceptions import ItemNotFoundError

from ol_openedx_course_translations import tasks

FAKE_KEY = "not-a-real-key"  # pragma: allowlist secret
SOURCE = "<problem><p>Hello</p></problem>"
TRANSLATED = "<problem><p>नमस्ते</p></problem>"

# The command tests translate this instead of the real benchmark: small, and
# its two text units make a mis-joined candidate visible.
BENCHMARK = (
    # An html block's body: a fragment with no single root, which is why the
    # benchmark parses as HTML rather than XML. The alt attribute keeps an
    # attribute-valued unit in play, as production translates those too.
    "<h4>Heat Transfer</h4>"
    "<p>Conduction moves heat through solid material.</p>"
    '<p><img src="d.png" alt="A diagram of conduction"/></p>'
    "<p>Radiation needs no medium at all.</p>"
)
BLOCK_ID = "block-v1:MITx+15.071x+2T2020+type@html+block@benchmark1"
WINNER = "openai/gpt-test"

# The block as a task receives it. An empty unit set is load-bearing where a
# test patches cached_benchmark: the translate gate rejects an arm whose every
# unit came back unchanged, and no unit is unchanged against no units.
BENCHMARK_BLOCK = Benchmark(
    block_id=BLOCK_ID,
    display_name="Heat Transfer",
    content=BENCHMARK,
    units=frozenset(),
)

BENCHMARK_TASKS = [
    tasks.benchmark_translate_task,
    tasks.benchmark_validate_task,
    tasks.benchmark_score_task,
    tasks.benchmark_rank_task,
]


@pytest.fixture
def judge():
    return OpenAIProvider("test-key", "gpt-test")


def _response(text):
    return mock.Mock(choices=[mock.Mock(message=mock.Mock(content=text))])


def _wrapped(payload):
    return (
        f"{llm_providers.TRANSLATION_MARKER_START}\n"
        f"{payload}\n"
        f"{llm_providers.TRANSLATION_MARKER_END}"
    )


def _rate(judge, reply):
    with mock.patch.object(llm_providers, "completion", return_value=_response(reply)):
        return judge.rate_translation(
            source_language="en",
            target_language="hi",
            source_content=SOURCE,
            translated_content=TRANSLATED,
        )


def _rank(judge, reply, candidates):
    with mock.patch.object(llm_providers, "completion", return_value=_response(reply)):
        return judge.rank_translations(
            source_language="en",
            target_language="hi",
            source_content=SOURCE,
            candidates=candidates,
        )


# ------------------------------------------------------------------ parsing


def test_scores_are_read_from_a_well_formed_reply(judge):
    result = _rate(
        judge,
        _wrapped(
            '{"accuracy": 8, "fluency": 7, "terminology": 9, "justification": "ok"}'
        ),
    )

    assert result.scores == {"accuracy": 8, "fluency": 7, "terminology": 9}
    assert result.justification == "ok"


def test_scores_survive_a_fenced_and_chatty_reply(judge):
    """Models add prose and code fences whatever the prompt says."""
    reply = (
        "Sure! Here is my assessment:\n"
        "```json\n"
        '{"accuracy": 6, "fluency": 5, "terminology": 7, "justification": "fine"}\n'
        "```\n"
        "Let me know if you need more detail."
    )

    assert _rate(judge, reply).scores["accuracy"] == 6  # noqa: PLR2004


@pytest.mark.parametrize(
    "reply",
    [
        (
            '{"accuracy": 8, "fluency": 7, "terminology": 9, "justification": "ok"}'
            " hope that helps :}"
        ),
        (
            'Here: {"accuracy": 8, "fluency": 7, "terminology": 9,'
            ' "justification": "ok"}  {thumbs up}'
        ),
    ],
)
def test_a_brace_in_the_trailing_prose_does_not_cost_the_judge(judge, reply):
    """
    A failed parse drops that judge from the whole scoring pass.

    Slicing to the last ``}`` in the reply swallows the prose after the object,
    so a sign-off containing a brace made the whole reply unparseable.
    """
    assert _rate(judge, reply).scores["accuracy"] == 8  # noqa: PLR2004


def test_a_revised_second_rating_is_rejected_rather_than_scored(judge):
    """
    Taking the first object silently would score a draft the judge retracted.

    A wrong score that looks right is the failure this command exists to
    avoid, so an ambiguous reply is rejected and the judge is dropped.
    """
    with pytest.raises(ValueError, match="more than one JSON object"):
        _rate(
            judge,
            '{"accuracy": 1, "fluency": 1, "terminology": 1, "justification": "a"}'
            ' revised: {"accuracy": 9, "fluency": 9, "terminology": 9,'
            ' "justification": "b"}',
        )


def test_an_unparseable_reply_is_rejected(judge):
    """One failure channel: an untrustworthy reply raises, like an API error."""
    with pytest.raises(ValueError, match="no JSON object"):
        _rate(judge, "I would rather not score this one.")


def test_a_reply_whose_json_is_malformed_is_rejected_as_a_value_error(judge):
    """
    Callers catch ValueError, and JSONDecodeError reaching one uncaught
    would take down the stage instead of dropping the judge.
    """
    with pytest.raises(ValueError, match="unparseable judge response"):
        _rate(judge, '{"accuracy": 8, "fluency":}')


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("<p>hi</p>", True),
        ("<br/>", True),
        # A comparison is not a tag; treating it as one re-parses prose as a
        # DOM, and the validator gate reads this to decide whether an arm
        # came back as markup at all.
        ("true if a < b and c > d", False),
        ("", False),
    ],
)
def test_markup_is_told_from_prose_that_merely_has_angle_brackets(value, expected):
    assert looks_like_markup(value) is expected


@pytest.mark.parametrize("value", [11, 0, '"high"', 4.5, "true", "false"])
def test_a_score_outside_the_scale_is_rejected(judge, value):
    payload = (
        f'{{"accuracy": {value}, "fluency": 7, "terminology": 9, "justification": "x"}}'
    )

    with pytest.raises(ValueError, match="accuracy"):
        _rate(judge, _wrapped(payload))


def test_a_missing_criterion_is_rejected(judge):
    with pytest.raises(ValueError, match="terminology"):
        _rate(judge, _wrapped('{"accuracy": 8, "fluency": 7}'))


def test_an_empty_completion_is_rejected(judge):
    """A refusal or a length cut-off returns no content at all."""
    with (
        mock.patch.object(llm_providers, "completion", return_value=_response(None)),
        pytest.raises(ValueError, match="no content"),
    ):
        judge._call_llm("system", "user")  # noqa: SLF001


def test_api_errors_reach_the_caller(judge):
    error = BadRequestError(
        message="upstream exploded", model="gpt-test", llm_provider="openai"
    )
    with (
        mock.patch.object(llm_providers, "completion", side_effect=error),
        pytest.raises(BadRequestError),
    ):
        judge.rate_translation(
            source_language="en",
            target_language="hi",
            source_content=SOURCE,
            translated_content=TRANSLATED,
        )


def test_candidates_reach_the_judge_anonymized_and_in_order(judge):
    """
    If a provider name leaks into the prompt, every number is contaminated by
    brand preference — and if the labels slip, the ranks land on the wrong
    candidates. Distinct texts here so both are actually checked.
    """
    with mock.patch.object(
        llm_providers,
        "completion",
        return_value=_response(_wrapped('{"ranks": {"A": 2, "B": 1}}')),
    ) as completion:
        ranks = judge.rank_translations(
            source_language="en",
            target_language="hi",
            source_content=SOURCE,
            candidates={"A": "<p>first</p>", "B": "<p>second</p>"},
        )

    sent = " ".join(
        message["content"] for message in completion.call_args.kwargs["messages"]
    )
    assert "CANDIDATE A" in sent
    assert sent.index("first") < sent.index("second")
    assert not any(
        name in sent for name in ("openai", "gemini", "anthropic", "mistral")
    )
    assert ranks == {"A": 2, "B": 1}


def test_a_rank_for_a_label_never_sent_is_rejected(judge):
    with pytest.raises(ValueError, match="unknown label"):
        _rank(
            judge,
            _wrapped('{"ranks": {"A": 1, "B": 2, "D": 3}}'),
            {"A": TRANSLATED, "B": TRANSLATED},
        )


@pytest.mark.parametrize(
    "payload",
    ['{"ranks": {"A": 0, "B": 1}}', '{"ranks": {"A": 1, "B": 3}}', '{"ranks": [1, 2]}'],
)
def test_a_rank_outside_the_shortlist_is_rejected(judge, payload):
    """``rank_one_votes`` leans on the parser bounding every rank."""
    with pytest.raises(ValueError, match="rank"):
        _rank(judge, _wrapped(payload), {"A": TRANSLATED, "B": TRANSLATED})


def test_a_missing_rank_is_rejected(judge):
    """Without this the final comprehension would raise KeyError mid-lane."""
    with pytest.raises(ValueError, match="no rank for label"):
        _rank(
            judge,
            _wrapped('{"ranks": {"A": 1}}'),
            {"A": TRANSLATED, "B": TRANSLATED},
        )


def test_anthropic_provider_prefixes_the_model():
    assert (
        AnthropicProvider("key", "claude-opus-5").model_name
        == "anthropic/claude-opus-5"
    )


def test_anthropic_provider_requires_a_model():
    with pytest.raises(ValueError, match="model_name is required"):
        AnthropicProvider("key")


# -------------------------------------------------------------- aggregation


def test_tied_scores_share_a_fractional_position():
    """
    Two candidates a judge cannot separate must not be separated by luck.

    The tie leads, so the candidate after it also has to land correctly:
    advancing by one instead of by the size of the tied group is invisible
    when the tie is last.
    """
    a, b, c = Candidate("a"), Candidate("b"), Candidate("c")
    rows = {row.candidate: row for row in build_rows({"j1": {a: 9.0, b: 9.0, c: 8.0}})}

    assert rows[a].mean_rank == rows[b].mean_rank == 1.5  # noqa: PLR2004
    assert rows[c].mean_rank == 3.0  # noqa: PLR2004


def test_mean_rank_is_a_mean_not_a_best_or_worst():
    """Positions 1 and 2 average to 1.5; min would be 1.0 and max 2.0."""
    a, b = Candidate("a"), Candidate("b")
    rows = {
        row.candidate: row
        for row in build_rows({"j1": {a: 9.0, b: 7.0}, "j2": {a: 6.0, b: 8.0}})
    }

    assert rows[a].mean_rank == rows[b].mean_rank == 1.5  # noqa: PLR2004
    assert rows[a].spread == 1.0


def test_mean_score_and_rank_average_over_the_judges_present():
    """The admin aggregates stored rows, so partial coverage must hold up."""
    a, b = Candidate("a"), Candidate("b")
    rows = {
        row.candidate: row
        for row in build_rows({"j1": {a: 9.0, b: 7.0}, "j2": {a: 6.0}})
    }

    assert rows[a].judges == 2  # noqa: PLR2004
    assert rows[a].mean_score == 7.5  # noqa: PLR2004
    assert rows[a].mean_rank == 1.0
    assert rows[b].judges == 1
    # Averaged over j1 alone, not over j2 as a zero.
    assert rows[b].mean_score == 7.0  # noqa: PLR2004
    assert rows[b].mean_rank == 2.0  # noqa: PLR2004


def test_the_best_mean_rank_sorts_first():
    a, b = Candidate("a"), Candidate("b")

    rows = build_rows({"j1": {a: 4.0, b: 9.0}, "j2": {a: 5.0, b: 8.0}})

    assert [row.candidate for row in rows] == [b, a]


def test_shortlist_keeps_candidates_tied_at_the_boundary():
    rows = [
        CandidateRow(candidate=Candidate(name), mean_score=0, positions={"j1": rank})
        for name, rank in [("a", 1.0), ("b", 2.0), ("c", 3.0), ("d", 3.0), ("e", 5.0)]
    ]

    shortlisted = [row.candidate.translator for row in select_shortlist(rows, size=3)]

    assert shortlisted == ["a", "b", "c", "d"]


def test_shortlist_stops_at_size_when_nothing_is_tied():
    """Without this the tie in the case above hides an off-by-one cutoff."""
    rows = [
        CandidateRow(candidate=Candidate(name), mean_score=0, positions={"j1": rank})
        for name, rank in [("a", 1.0), ("b", 2.0), ("c", 3.0), ("d", 4.0), ("e", 5.0)]
    ]

    assert [row.candidate.translator for row in select_shortlist(rows, size=3)] == [
        "a",
        "b",
        "c",
    ]


def test_shortlist_cap_truncates_a_tie_wider_than_the_cap():
    rows = [
        CandidateRow(
            candidate=Candidate(str(index)), mean_score=0, positions={"j1": 1.0}
        )
        for index in range(10)
    ]

    assert len(select_shortlist(rows, size=5, cap=8)) == 8  # noqa: PLR2004


def test_a_judge_that_ties_for_first_casts_no_vote():
    """
    Counting both would let one judge outvote a denominator of judges.

    The prompt permits ties, so a judge naming two bests is a valid reply — it
    simply has not named one.
    """
    a, b = Candidate("a"), Candidate("b")

    votes = rank_one_votes({"j1": {a: 1, b: 1}, "j2": {a: 1, b: 2}})

    assert votes == {a: 1}


def test_the_comparative_winner_is_the_lowest_mean_rank():
    """One pass, one signal: the best mean comparative rank wins outright."""
    a, b, c = Candidate("a"), Candidate("b"), Candidate("c")
    rows = build_comparative_rows({"j1": {a: 2, b: 1, c: 3}, "j2": {a: 1, b: 2, c: 3}})

    # a and b both average 1.5, so nothing in this mode can separate them.
    winner, reason = pick_comparative_winner(rows)
    assert winner is None
    assert "tied" in reason

    decisive = build_comparative_rows({"j1": {a: 2, b: 1}, "j2": {a: 3, b: 1}})
    winner, reason = pick_comparative_winner(decisive)
    assert winner == b
    assert "lowest mean comparative rank" in reason


def test_comparative_rows_average_the_ranks_as_given():
    """
    Ranks are already positions on one shared scale from a single call.

    Converting them again, the way build_rows must for absolute scores, would
    discard the margin between 1st and 6th that the judge actually expressed.
    """
    a, b = Candidate("a"), Candidate("b")
    rows = build_comparative_rows({"j1": {a: 1, b: 6}, "j2": {a: 2, b: 5}})

    by_candidate = {row.candidate: row for row in rows}
    assert by_candidate[a].mean_rank == 1.5  # noqa: PLR2004
    assert by_candidate[b].mean_rank == 5.5  # noqa: PLR2004
    assert by_candidate[a].spread == 1.0
    assert by_candidate[a].mean_score is None


def test_a_judge_that_did_not_rank_a_candidate_is_not_counted_for_it():
    """A candidate one judge never ranked averages over the rest."""
    a, b = Candidate("a"), Candidate("b")
    rows = build_comparative_rows({"j1": {a: 1, b: 2}, "j2": {a: 3}})

    by_candidate = {row.candidate: row for row in rows}
    assert by_candidate[a].judges == 2  # noqa: PLR2004
    assert by_candidate[b].judges == 1
    assert by_candidate[b].mean_rank == 2.0  # noqa: PLR2004


def test_no_ranks_at_all_is_not_a_winner():
    assert pick_comparative_winner([]) == (None, "no candidates were ranked")


# ------------------------------------------------------------- the command


def _timeout(spec):
    return Timeout(message="upstream timed out", model=spec, llm_provider="test")


class FakeProvider:
    """
    A scripted provider whose output says which translator produced it.

    Structure is preserved through translation and validation, because the
    command rejects an arm whose element count changes.
    """

    # Every instance built during a test, so a test can assert what the tasks
    # actually hand a provider rather than only what comes back.
    all_providers: ClassVar[list] = []

    def __init__(self, spec, *, mode=None):
        self.spec = spec
        self.mode = mode
        self.calls = []
        FakeProvider.all_providers.append(self)

    def translate_text(self, source_content, _target_language, **kwargs):
        self.calls.append(("translate", kwargs | {"source_content": source_content}))
        if self.mode == "translate_times_out":
            raise _timeout(self.spec)
        if self.mode == "translate_raises":
            msg = "upstream refused"
            raise RuntimeError(msg)
        if self.mode == "translate_echoes":
            return source_content
        if self.mode == "translate_empty":
            return ""
        if self.mode == "translate_untranslatable":
            # Markup the parser reads but finds no translatable unit in.
            return '<p><img src="d.png"/></p>'
        if self.mode == "translate_drops_markers":
            # What translate_text returns when a batch reply arrives without
            # its :::N::: ids: every unit falls back to the original, and the
            # document is reserialized, so it is English but not byte-identical.
            helper = HtmlXmlTranslationHelper(is_xml=False)
            root, units, refs = helper.extract_units(source_content)
            return helper.serialize(helper.apply_translations(root, refs, list(units)))
        if self.mode == "translate_partial":
            # Only the heading is translated; the paragraphs and the alt text
            # stay English, which is what the diagnostic column reports.
            return source_content.replace("Heat Transfer", f"CALOR[{self.spec}]")
        return (
            source_content.replace("Conduction moves", f"CONDUCCION[{self.spec}]")
            .replace("Radiation needs", f"RADIACION[{self.spec}]")
            .replace("A diagram of", f"DIAGRAMA[{self.spec}] de")
            .replace("Heat Transfer", f"CALOR[{self.spec}]")
        )

    def validate_translation(self, *, translated_content, **kwargs):
        self.calls.append(("validate", kwargs))
        if self.mode == "validator_times_out":
            raise _timeout(self.spec)
        if self.mode == "validator_prose":
            return "Looks good to me!"
        if self.mode == "validator_restructures":
            return translated_content + "<p>extra</p>"
        return translated_content.replace("CONDUCCION", "CONDUCCION!")

    def rate_translation(self, *, translated_content, **kwargs):
        self.calls.append(("score", kwargs))
        if self.mode == "score_times_out":
            raise _timeout(self.spec)
        if self.mode == "score_rejects":
            msg = "unparseable"
            raise ValueError(msg)
        if self.mode == "score_rejects_per_arm":
            # A different message per arm, so which one is kept is visible.
            msg = f"unparseable at {translated_content[:30]}"
            raise ValueError(msg)
        if self.mode == "score_rejects_one_translator" and WINNER in translated_content:
            # Fails on some arms and not others, which is what the whole-pass
            # exclusion exists to handle.
            msg = "unparseable on this candidate"
            raise ValueError(msg)
        base = sum(translated_content.encode()) % 5
        return Rating(
            scores={
                "accuracy": 5 + base,
                "fluency": 5 + (base + 1) % 5,
                "terminology": 5 + (base + 2) % 5,
            },
            justification=f"scored by {self.spec}",
        )

    def rank_translations(self, *, candidates, **kwargs):
        self.calls.append(("rank", kwargs))
        if self.mode == "rank_times_out":
            raise _timeout(self.spec)
        if self.mode == "rank_rejects":
            msg = "unparseable ranking"
            raise ValueError(msg)
        # Rank 1 goes to the candidate WINNER translated, so a rotated label
        # map lands the rank on the wrong candidate and the test fails.
        ordered = sorted(
            candidates, key=lambda label: (WINNER not in candidates[label], label)
        )
        return {label: position for position, label in enumerate(ordered, start=1)}


@pytest.fixture
def _providers(settings):
    settings.TRANSLATIONS_PROVIDERS = {
        "default_provider": "openai",
        "openai": {"api_key": FAKE_KEY, "default_model": "gpt-test"},
        "gemini": {"api_key": FAKE_KEY, "default_model": "gemini-test"},
        "mistral": {"api_key": "", "default_model": "mistral-test"},
    }
    settings.COURSE_TRANSLATIONS_SUPPORTED_LANGUAGES = {"en": "English", "hi": "Hindi"}


@pytest.fixture
def benchmark_block():
    """Serve a published html block wherever read_benchmark looks for one."""
    block = mock.Mock(data=BENCHMARK, display_name="Heat Transfer")
    store = mock.Mock()
    store.get_item.return_value = block
    with mock.patch("xmodule.modulestore.django.modulestore", return_value=store):
        yield store


@pytest.fixture(autouse=True)
def _reset_provider_calls():
    """Recorded calls are per test, not per session."""
    FakeProvider.all_providers.clear()


@pytest.fixture(autouse=True)
def _eager_celery():
    """Run benchmark tasks in-process, so a stage is still one call away."""
    app = current_app._get_current_object()  # noqa: SLF001
    previous = app.conf.task_always_eager, app.conf.task_eager_propagates
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = False
    yield
    app.conf.task_always_eager, app.conf.task_eager_propagates = previous


SPEC = "openai/gpt-test"

# Per stage: how to invoke the task, a mode whose failure is transient, and a
# mode whose failure is not. `arm` is the row under test, `source` a row that
# already holds content for the stages that read one.
BENCHMARK_STAGES = {
    "translate": (
        lambda arm, source: tasks.benchmark_translate_task(
            arm.pk, SPEC, "hi", source.run.pk
        ),
        "translate_times_out",
        "translate_raises",
    ),
    "validate": (
        lambda arm, source: tasks.benchmark_validate_task(
            arm.pk, source.pk, SPEC, "hi", source.run.pk
        ),
        "validator_times_out",
        "validator_prose",
    ),
    "score": (
        lambda arm, source: tasks.benchmark_score_task(
            arm.pk, SPEC, "hi", source.run.pk
        ),
        "score_times_out",
        "score_rejects",
    ),
    "rank": (
        lambda _arm, source: tasks.benchmark_rank_task(
            SPEC, {"A": source.pk}, "hi", source.run.pk
        ),
        "rank_times_out",
        "rank_rejects",
    ),
}


@pytest.fixture
def benchmark_arms(db):  # noqa: ARG001
    """One empty arm and one already holding content, for the stage tasks."""
    run = TranslationQualityRun.objects.create(
        target_language="hi",
        benchmark_block_id=BLOCK_ID,
        translators_arg=SPEC,
        judges_arg=SPEC,
    )
    source = TranslationQualityCandidate.objects.create(
        run=run, translator=SPEC, validator="", translated_content=BENCHMARK
    )
    arm = TranslationQualityCandidate.objects.create(
        run=run, translator=SPEC, validator=SPEC
    )
    return arm, source


def _run(modes=None, *, confirm=True, **options):
    """Run the command with every provider replaced by a scripted fake."""
    modes = modes or {}
    out = StringIO()
    options.setdefault("benchmark_block", BLOCK_ID)

    def build(provider, model):
        spec = f"{provider}/{model}"
        return FakeProvider(spec, mode=modes.get(spec))

    with mock.patch(
        "ol_openedx_course_translations.tasks.get_translation_provider",
        side_effect=build,
    ) as factory:
        call_command(
            "rate_translation_quality",
            target_language="hi",
            yes=confirm,
            stdout=out,
            **options,
        )
    return out.getvalue(), factory


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_a_run_records_every_candidate_and_score():
    _run(translators="openai,gemini", judges="openai,gemini")

    run = TranslationQualityRun.objects.get()
    candidates = TranslationQualityCandidate.objects.filter(run=run)

    # 2 translators x 2 validators; the unvalidated arms are scaffolding and
    # are deleted once the validators have read them.
    assert candidates.count() == 4  # noqa: PLR2004
    assert not candidates.filter(validator="").exists()
    assert TranslationQualityScore.objects.count() == 8  # noqa: PLR2004
    assert run.target_language == "hi"
    assert run.judges_arg == "openai/gpt-test,gemini/gemini-test"


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_the_first_place_rank_lands_on_the_candidate_the_judge_chose():
    """
    The label -> candidate join, end to end.

    Each judge ranks whichever anonymised label carries WINNER's translation
    first, so every stored rank-1 row must belong to a WINNER-translated
    candidate. Rotating the label map by one breaks this and nothing else.
    """
    _run(translators="openai,gemini", judges="openai,gemini")

    firsts = TranslationQualityScore.objects.filter(comparative_rank=1)

    assert firsts.count() == 2  # one per judge  # noqa: PLR2004
    assert {score.candidate.translator for score in firsts} == {WINNER}


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_each_judge_labels_the_shortlist_bijectively():
    _run(translators="openai,gemini", judges="openai,gemini")

    ranked = TranslationQualityScore.objects.exclude(comparative_rank=None)
    per_judge: dict[str, list[str]] = {}
    for score in ranked:
        per_judge.setdefault(score.judge, []).append(score.comparative_label)

    assert per_judge
    for labels in per_judge.values():
        assert len(set(labels)) == len(labels)
        assert all(label for label in labels)


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_an_untranslated_document_is_excluded_rather_than_scored():
    """
    translate_text hands back the source on failure.

    Without the unchanged check that English document becomes a candidate and
    gets a quality score.
    """
    output, _ = _run(
        modes={"gemini/gemini-test": "translate_echoes"},
        translators="openai,gemini",
        judges="openai",
    )

    broken = TranslationQualityCandidate.objects.exclude(error="")
    assert broken.count() == 2  # every arm of that translator  # noqa: PLR2004
    assert {candidate.translator for candidate in broken} == {"gemini/gemini-test"}
    assert not TranslationQualityScore.objects.filter(
        candidate__translator="gemini/gemini-test"
    ).exists()
    assert "source unchanged" in output


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_a_reserialized_but_untranslated_document_is_excluded():
    """
    The arm gate cannot be a byte comparison.

    translate_text keeps the original unit whenever a batch reply loses its
    :::N::: markers and then reserializes, so the document differs from the
    source in whitespace while being entirely English. Byte-compared, this arm
    is scored as a bad translation instead of reported as a failed one.
    """
    output, _ = _run(
        modes={"gemini/gemini-test": "translate_drops_markers"},
        translators="openai,gemini",
        judges="openai",
    )

    broken = TranslationQualityCandidate.objects.exclude(error="")
    assert {candidate.translator for candidate in broken} == {"gemini/gemini-test"}
    assert not TranslationQualityScore.objects.filter(
        candidate__translator="gemini/gemini-test"
    ).exists()
    assert "source unchanged" in output


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_a_translator_failure_still_records_all_of_its_arms():
    _run(
        modes={"gemini/gemini-test": "translate_raises"},
        translators="openai,gemini",
        judges="openai",
    )

    arms = TranslationQualityCandidate.objects.filter(translator="gemini/gemini-test")

    assert arms.count() == 2  # noqa: PLR2004
    # The source row that carried the provider's message is gone, so each arm
    # has to say both that it never ran and why.
    assert all("translation failed" in arm.error for arm in arms)
    assert all("upstream refused" in arm.error for arm in arms)


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
@pytest.mark.parametrize(
    ("mode", "expected"),
    [("validator_prose", "no markup"), ("validator_restructures", "markup structure")],
)
def test_unusable_validator_output_is_excluded_rather_than_scored(mode, expected):
    output, _ = _run(
        modes={"gemini/gemini-test": mode},
        translators="openai,gemini",
        judges="openai",
    )

    broken = TranslationQualityCandidate.objects.exclude(error="")

    assert {candidate.validator for candidate in broken} == {"gemini/gemini-test"}
    assert expected in output
    assert not TranslationQualityScore.objects.filter(
        candidate__validator="gemini/gemini-test"
    ).exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_a_judge_that_fails_anywhere_is_dropped_from_scoring_and_announced():
    """
    Partial credit would rank candidates over different judge sets, so one bad
    reply costs that judge every row — and the operator has to be told, or a
    complete-looking table quietly rests on fewer judges.
    """
    output, _ = _run(
        modes={"gemini/gemini-test": "score_rejects"},
        translators="openai,gemini",
        judges="openai,gemini",
    )

    scores = TranslationQualityScore.objects.all()

    assert {score.judge for score in scores} == {WINNER}
    assert "gemini/gemini-test dropped" in output
    assert "unparseable" in output


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_a_ranking_failure_costs_only_the_comparative_pass():
    """
    Mean rank comes from the scoring pass, so discarding those scores would
    shrink the judge set every candidate is ranked over — worse than losing
    one set of first-place votes.
    """
    output, _ = _run(
        modes={"gemini/gemini-test": "rank_rejects"},
        translators="openai,gemini",
        judges="openai,gemini",
    )

    scores = TranslationQualityScore.objects.all()
    ranked_judges = {score.judge for score in scores.exclude(comparative_rank=None)}

    assert {score.judge for score in scores} == {WINNER, "gemini/gemini-test"}
    assert ranked_judges == {WINNER}
    assert "ranking failed" in output
    # The numerator is the judges that came back, the denominator those asked.
    assert "(1 of 2 judge(s) ranked)" in output
    # The verdict comes from the comparative pass, so the judge that did rank
    # decides; the one that failed keeps its scores and loses only its ranks.
    assert "Winner:" in output
    # The label belongs to a completed ranking only.
    assert (
        not scores.filter(judge="gemini/gemini-test")
        .exclude(comparative_label="")
        .exists()
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_a_repeated_roster_entry_is_collapsed():
    """'openai' and 'openai/gpt-test' are the same spec once resolved."""
    _run(translators="openai,openai/gpt-test", judges="openai")

    candidates = TranslationQualityCandidate.objects.all()

    assert candidates.count() == 1
    assert {candidate.translator for candidate in candidates} == {WINNER}
    # The dedupe is only observable here and in the pre-flight estimate.
    assert TranslationQualityRun.objects.get().translators_arg == WINNER


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_the_default_roster_skips_providers_without_a_key():
    output, _ = _run()

    run = TranslationQualityRun.objects.get()

    assert run.translators_arg == "openai/gpt-test,gemini/gemini-test"
    assert run.judges_arg == "openai/gpt-test,gemini/gemini-test"
    assert "skipped translator mistral: no api_key" in output


@pytest.mark.usefixtures("_providers")
def test_the_default_roster_keeps_azure_without_a_key(settings):
    """Azure authenticates with an Entra token, so it never has an api_key."""
    settings.TRANSLATIONS_PROVIDERS["azure"] = {"default_model": "gpt-azure"}

    roster = benchmark_command.Command()._resolve_roster("", "translator")  # noqa: SLF001

    assert "azure/gpt-azure" in roster


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_a_provider_named_by_hand_but_unconfigured_is_fatal():
    """Silently skipping it would answer a different question than the one asked."""
    with pytest.raises(CommandError, match="Unknown translator provider 'opneai'"):
        _run(translators="opneai", judges="openai")


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
@pytest.mark.parametrize("answer", ["n", "", "maybe", "yes please"])
def test_declining_the_prompt_spends_nothing(answer):
    """Only an explicit yes may spend; a bare Enter is not one."""
    with (
        mock.patch("builtins.input", return_value=answer) as prompt,
        pytest.raises(CommandError, match="Aborted"),
    ):
        _run(confirm=False, translators="openai", judges="openai")

    assert prompt.called
    assert not TranslationQualityRun.objects.exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
@pytest.mark.parametrize("answer", ["y", "YES", " y "])
def test_an_explicit_yes_proceeds(answer):
    """Surrounding space and case are normalised, so these must still spend."""
    with mock.patch("builtins.input", return_value=answer):
        _run(confirm=False, translators="openai", judges="openai")

    assert TranslationQualityRun.objects.exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_a_non_interactive_prompt_aborts_rather_than_assuming_yes():
    """Unattended without --yes must stop, not spend on a default."""
    with (
        mock.patch("builtins.input", side_effect=EOFError),
        pytest.raises(CommandError, match="--yes"),
    ):
        _run(confirm=False, translators="openai", judges="openai")

    assert not TranslationQualityRun.objects.exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_the_estimated_candidate_count_matches_what_the_run_produces():
    """An operator approves the run on this number, so it must not drift."""
    output, _ = _run(translators="openai,gemini", judges="openai")

    estimated = int(
        next(
            line.split(":")[1].strip()
            for line in output.splitlines()
            if line.startswith("Candidates:")
        )
    )

    assert estimated == TranslationQualityCandidate.objects.count()


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_the_admin_report_ranks_the_same_way_the_command_does():
    """
    The admin re-derives the standings from stored rows.

    Swapping its two aggregation levels renders a plausible table built from
    judges-as-candidates, which only an assertion on the leader catches.
    """
    _run(translators="openai,gemini", judges="openai,gemini")
    run = TranslationQualityRun.objects.get()
    assert not run.comparative_only

    html = TranslationQualityRunAdmin(TranslationQualityRun, mock.Mock()).report(run)
    rendered = [row for row in html.split("<tr>") if "<td>" in row]

    expected = build_rows(
        {
            score.judge: {
                Candidate(other.candidate.translator, other.candidate.validator): fmean(
                    (other.accuracy, other.fluency, other.terminology)
                )
                for other in TranslationQualityScore.objects.filter(judge=score.judge)
            }
            for score in TranslationQualityScore.objects.all()
        }
    )

    # Only scored candidates appear: a broken arm has no scores to aggregate.
    assert len(rendered) == len(expected)
    for row, expected_row in zip(rendered, expected, strict=True):
        assert f"<td>{expected_row.candidate}</td>" in row
        assert f"<td>{expected_row.mean_rank:.2f}</td>" in row
        assert f"<td>{expected_row.mean_score:.2f}</td>" in row


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_the_admin_report_shows_each_judge_and_the_verdict():
    """
    The aggregate alone lets a reader crown the top row.

    Mean rank comes only from the scoring pass, so a candidate can lead the
    table while both judges ranked it low head to head. The per-judge columns
    and the verdict are what make that visible in the stored record.
    """
    _run(translators="openai,gemini", judges="openai,gemini")
    run = TranslationQualityRun.objects.get()
    assert not run.comparative_only

    html = TranslationQualityRunAdmin(TranslationQualityRun, mock.Mock()).report(run)

    for judge in ("openai/gpt-test", "gemini/gemini-test"):
        assert f"<th>{judge}</th>" in html
    # position · accuracy/fluency/terminology, and a #rank for the shortlist.
    assert re.search(r"<td>\d+\.\d · \d+/\d+/\d+", html)
    assert "· #1" in html
    assert "Verdict:" in html
    # The admin recomputes the verdict from stored ranks. If it failed to
    # collect them the line would still render, saying nothing was ranked.
    assert "no candidates were ranked" not in html


def _standings(output):
    """Parse the printed standings table into (candidate, rank, score, judges)."""
    lines = output.splitlines()
    start = next(
        index for index, line in enumerate(lines) if line.startswith("candidate")
    )
    rows = []
    for line in lines[start + 2 :]:
        if not line.strip() or line.startswith("'unchanged'"):
            break
        fields = re.split(r"\s{2,}", line.strip())
        rows.append((fields[0], float(fields[1]), float(fields[2]), int(fields[4])))
    return rows


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_the_printed_standings_are_ordered_and_per_judge():
    """
    The table the operator reads, read back.

    Nothing else asserts the report body, so a reversed ordering, a merged
    pseudo-judge, or every judge scoring the English source instead of the
    candidate would all print a confident, plausible, wrong table.
    """
    output, _ = _run(translators="openai,gemini", judges="openai,gemini")
    rows = _standings(output)

    assert len(rows) == TranslationQualityCandidate.objects.count()
    # Best first.
    assert [row[1] for row in rows] == sorted(row[1] for row in rows)
    # Every candidate was scored by both judges, not by one merged pseudo-judge.
    assert {row[3] for row in rows} == {2}
    # Judges scored the candidates, not the identical source document.
    assert len({row[2] for row in rows}) > 1
    assert all("→" in row[0] for row in rows)


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_the_verdict_line_names_a_candidate_or_declines():
    """`Winner: None` would be printed in green by an inverted branch."""
    output, _ = _run(translators="openai,gemini", judges="openai,gemini")

    verdict = next(
        line
        for line in output.splitlines()
        if line.startswith(("Winner:", "No clear winner"))
    )

    assert verdict.startswith("No clear winner") or "→" in verdict


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_a_judge_that_fails_on_one_candidate_keeps_none_of_its_rows():
    """
    The all-or-nothing rule, with good rows available to leak.

    The judge here fails on the two arms one translator produced and succeeds
    on the other two; partial credit would rank candidates over uneven judge
    sets, which is exactly what mean rank cannot absorb.
    """
    output, _ = _run(
        modes={"gemini/gemini-test": "score_rejects_one_translator"},
        translators="openai,gemini",
        judges="openai,gemini",
    )

    assert not TranslationQualityScore.objects.filter(
        judge="gemini/gemini-test"
    ).exists()
    assert TranslationQualityScore.objects.filter(judge=WINNER).exists()
    assert "gemini/gemini-test dropped" in output
    # The stored run records why, not merely the absence of its scores.
    stored = TranslationQualityRun.objects.get().excluded_judges
    assert stored.startswith("gemini/gemini-test:")
    assert "unparseable on this candidate" in stored


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_a_judge_dropped_from_scoring_is_not_asked_to_rank():
    """Its ranking call would be paid for and then discarded."""
    output, _ = _run(
        modes={"gemini/gemini-test": "score_rejects"},
        translators="openai,gemini",
        judges="openai,gemini",
    )

    ranked_judges = {
        score.judge
        for score in TranslationQualityScore.objects.exclude(comparative_rank=None)
    }

    assert ranked_judges <= {WINNER}
    assert "Judges dropped from scoring: gemini/gemini-test" in output
    # Only the surviving judge was asked, so the denominator is 1, not 2.
    assert "1 of 1 judge(s) ranked" in output


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers")
@pytest.mark.parametrize(
    ("block", "message"),
    [
        (None, "No published block at"),
        (mock.Mock(data=None), "no markup body"),
        (mock.Mock(data="   "), "no markup body"),
        (mock.Mock(data="<p><img src='a.png'/></p>"), "no translatable text"),
        # No element node at all: the parser returns no root, which used to
        # escape as an AttributeError the command does not catch.
        (mock.Mock(data="<!-- TODO write this -->"), "no translatable text"),
    ],
)
def test_an_unusable_block_is_named_as_the_cause(block, message):
    """
    Otherwise the run pays for N translations first, then blames them all.

    The block is live course content, so none of these can be ruled out by
    validating at authoring time the way a stored row could be.
    """
    store = mock.Mock()
    if block is None:
        store.get_item.side_effect = ItemNotFoundError("gone")
    else:
        store.get_item.return_value = block

    with (
        mock.patch("xmodule.modulestore.django.modulestore", return_value=store),
        pytest.raises(CommandError, match=message),
    ):
        _run(translators="openai", judges="openai")

    assert not TranslationQualityRun.objects.exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_the_translator_is_told_to_handle_the_content_as_html():
    """
    The whole point of reading a course block is that production translates
    an html block's body as HTML — tasks.py derives tag_handling from the
    file suffix. Nothing else in the suite observes the value the task
    passes, so the constant could be any string and the run would look fine.
    """
    _run(translators="openai", judges="openai")

    sent = [
        kwargs
        for provider in FakeProvider.all_providers
        for stage, kwargs in provider.calls
        if stage == "translate"
    ]

    assert sent
    assert all(call["tag_handling"] == "html" for call in sent)
    # Records that "html" is what production's suffix rule yields for an
    # html block. It re-states that rule rather than calling it, so it
    # documents the tie; it does not enforce it.
    assert Path("body.html").suffix.lstrip(".") == BENCHMARK_TAG_HANDLING


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_every_judge_and_validator_sees_the_benchmark_as_the_source():
    """
    A run compares translations against the source. If the tasks passed the
    wrong text — or none — every judge would score against nothing and the
    standings would still render, so this asserts the source reaches them.
    """
    _run(translators="openai,gemini", judges="openai")

    by_stage = {}
    for provider in FakeProvider.all_providers:
        for stage, kwargs in provider.calls:
            by_stage.setdefault(stage, []).append(kwargs)

    for stage in ("validate", "score", "rank"):
        assert by_stage.get(stage), f"no {stage} calls recorded"
        assert all(call["source_content"] == BENCHMARK for call in by_stage[stage]), (
            stage
        )


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers")
def test_the_display_name_falls_back_to_the_block_id():
    """Shown to whoever reads the run; an unnamed block must still say something."""
    store = mock.Mock()
    store.get_item.return_value = mock.Mock(data=BENCHMARK, display_name="")

    with mock.patch("xmodule.modulestore.django.modulestore", return_value=store):
        anonymous = benchmark_module.read_benchmark(BLOCK_ID)

    assert anonymous.display_name == "benchmark1"

    store.get_item.return_value = mock.Mock(data=BENCHMARK, display_name="Named")
    with mock.patch("xmodule.modulestore.django.modulestore", return_value=store):
        assert benchmark_module.read_benchmark(BLOCK_ID).display_name == "Named"


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers")
def test_only_an_html_block_can_be_benchmarked():
    """
    A problem block has a .data body too, but it exports as .xml and
    production translates it as XML. Benchmarking it as HTML would measure
    the very mismatch BENCHMARK_TAG_HANDLING exists to remove.
    """
    store = mock.Mock()
    store.get_item.return_value = mock.Mock(data="<problem><p>Pick one</p></problem>")
    problem = "block-v1:MITx+15.071x+2T2020+type@problem+block@p1"

    with (
        mock.patch("xmodule.modulestore.django.modulestore", return_value=store),
        pytest.raises(CommandError, match="only html blocks"),
    ):
        _run(translators="openai", judges="openai", benchmark_block=problem)


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers")
def test_a_v2_library_key_is_reported_not_asserted():
    """
    lb:... parses as a UsageKey, then MixedModuleStore asserts on it with an
    empty message rather than raising something a reader can act on.
    """
    store = mock.Mock()
    store.get_item.side_effect = AssertionError()

    with (
        mock.patch("xmodule.modulestore.django.modulestore", return_value=store),
        pytest.raises(CommandError, match="No published block at"),
    ):
        _run(
            translators="openai",
            judges="openai",
            benchmark_block="lb:MITx:mylib:html:intro",
        )


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers")
@pytest.mark.usefixtures("benchmark_block")
def test_a_translator_that_dies_outside_its_handler_records_why():
    """
    The task writes its own failures onto the row; one that died before its
    handler has to be written by the command, or every dependent arm reads
    "translation failed:" with nothing after the colon.

    Any failure outside the handler that is not a BenchmarkError is the
    case — a lost worker, a crash in the read — and whatever caused it, the
    arm is the thing that did not get done.
    """
    with (
        mock.patch(
            "ol_openedx_course_translations.tasks.cached_benchmark",
            side_effect=RuntimeError("worker went away"),
        ),
        pytest.raises(CommandError),
    ):
        _run(translators="openai", judges="openai")

    errors = {c.error for c in TranslationQualityCandidate.objects.all()}
    assert errors
    assert all("worker went away" in error for error in errors)
    assert not any(error.endswith(": ") for error in errors)


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers")
def test_an_unreadable_block_stops_the_run_instead_of_blaming_the_providers():
    """
    Every task reads the same block, so a block that cannot be read fails
    all of them.

    Letting that through as a per-task failure blames each translator in
    turn, then each judge, and writes those reasons onto the rows and onto
    the run's own excluded_judges — where they outlive the console and read
    as "every provider I have is broken".
    """
    block = mock.Mock(data=BENCHMARK, display_name="Heat Transfer")
    store = mock.Mock()
    # Two reads for the command; the block is gone by the time a task looks.
    store.get_item.side_effect = [block, block, *[ItemNotFoundError("gone")] * 20]

    with (
        mock.patch("xmodule.modulestore.django.modulestore", return_value=store),
        pytest.raises(CommandError, match="No published block at"),
    ):
        _run(translators="openai", judges="openai")

    assert not TranslationQualityCandidate.objects.exclude(error="").exists()
    assert TranslationQualityRun.objects.get().excluded_judges == ""


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers")
def test_a_malformed_usage_key_is_rejected_before_the_modulestore():
    """A typo in the key must not read as a missing block."""
    with pytest.raises(CommandError, match="is not a usage key"):
        _run(translators="openai", judges="openai", benchmark_block="not-a-key")


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers")
def test_the_published_revision_is_what_is_read(benchmark_block):
    """
    A Studio draft shifts under an author mid-run, and a course export
    carries the published text — so the benchmark must measure the same
    revision translate_course would.
    """
    _run(translators="openai", judges="openai")

    revisions = {
        call.kwargs["revision"] for call in benchmark_block.get_item.call_args_list
    }
    assert revisions == {ModuleStoreEnum.RevisionOption.published_only}
    assert TranslationQualityRun.objects.get().benchmark_block_id == BLOCK_ID


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_every_arm_failing_reports_the_reasons_before_giving_up():
    """The one message left must not name the wrong layer."""
    output = StringIO()

    def build(provider, model):
        return FakeProvider(f"{provider}/{model}", mode="translate_raises")

    with (
        mock.patch(
            "ol_openedx_course_translations.tasks.get_translation_provider",
            side_effect=build,
        ),
        pytest.raises(CommandError, match="No candidate was scored"),
    ):
        call_command(
            "rate_translation_quality",
            target_language="hi",
            benchmark_block=BLOCK_ID,
            yes=True,
            translators="openai",
            judges="openai",
            stdout=output,
        )

    assert "upstream refused" in output.getvalue()
    assert "candidate(s) excluded" in output.getvalue()


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_a_partial_translation_is_visible_in_the_diagnostic_column():
    """
    A document a third in English passes the unchanged-document check.

    The count is the only thing that shows it, so a low score is not silently
    read as the model's judgement.
    """
    output, _ = _run(
        modes={"gemini/gemini-test": "translate_partial"},
        translators="openai,gemini",
        judges="openai",
    )
    partial = [
        line for line in output.splitlines() if line.startswith("gemini/gemini-test →")
    ]

    assert partial
    # Three of the fixture's four units came back untouched.
    assert all(line.split()[-1] == "3" for line in partial)

    # And a fully translated arm reads 0, not the "could not measure" marker.
    whole = [
        line for line in output.splitlines() if line.startswith("openai/gpt-test →")
    ]
    assert whole
    assert all(line.split()[-1] == "0" for line in whole)


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_an_expected_arm_failure_is_logged_without_a_traceback(caplog):
    """
    A stack trace per rejected arm buries the report that summarises them.

    Only a bug-like exception earns a traceback; the arm gates raise
    RuntimeError and the report already names each one.
    """
    with caplog.at_level("WARNING"):
        _run(
            modes={"gemini/gemini-test": "validator_prose"},
            translators="openai,gemini",
            judges="openai",
        )

    job_failures = [
        record
        for record in caplog.records
        if record.msg.startswith("benchmark task failed")
    ]

    assert job_failures
    assert all(record.exc_info is None for record in job_failures)


def test_a_bug_like_failure_keeps_its_traceback(caplog):
    """The mirror of the case above: without it the branch can be deleted."""
    with caplog.at_level("WARNING"):
        tasks._log_benchmark_failure(AttributeError("typo"), "score x")  # noqa: SLF001
        tasks._log_benchmark_failure(RuntimeError("expected"), "score y")  # noqa: SLF001

    bug, expected = caplog.records
    assert bug.exc_info is not None
    assert expected.exc_info is None


@pytest.mark.django_db
@pytest.mark.usefixtures("benchmark_block")
def test_a_loader_parser_bug_is_not_reported_as_bad_content():
    """Only a parse failure is the block's fault; a bug here must escape."""
    with (
        mock.patch(
            "ol_openedx_course_translations.utils.benchmark.units_and_elements",
            side_effect=TypeError("extractor is broken"),
        ),
        pytest.raises(TypeError, match="extractor is broken"),
    ):
        benchmark_module.read_benchmark(BLOCK_ID)


@pytest.mark.django_db
@pytest.mark.usefixtures("benchmark_block")
@pytest.mark.parametrize("stage", list(BENCHMARK_STAGES))
def test_a_bad_benchmark_fails_the_task_instead_of_the_arm(benchmark_arms, stage):
    """
    Reading the benchmark sits outside every task's handler on purpose.

    Inside it, one unreadable benchmark is recorded as every translator or
    judge failing — N arms blaming N providers for one row. All four stages,
    because the first version of this covered only translate and the other
    three could be moved back inside undetected.
    """
    arm, source = benchmark_arms
    invoke = BENCHMARK_STAGES[stage][0]
    store = mock.Mock()
    store.get_item.side_effect = ItemNotFoundError("gone")

    with (
        mock.patch("xmodule.modulestore.django.modulestore", return_value=store),
        pytest.raises(BenchmarkError, match="No published block at"),
    ):
        invoke(arm, source)

    arm.refresh_from_db()
    assert arm.error == ""


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_the_benchmark_argument_is_required():
    """
    Nothing is bundled, so omitting it must read as a usage error rather
    than degrading into a confusing lookup failure.
    """
    with pytest.raises(CommandError, match=r"required.*--benchmark-block"):
        call_command(
            "rate_translation_quality",
            target_language="hi",
            yes=True,
            translators="openai",
            judges="openai",
        )


def test_comments_are_not_counted_as_elements():
    """
    The element count gates a validator's arm: counting a comment would make
    a validator that touched one look like it restructured the document.
    """
    # Inside the markup, not before it. A leading comment is discarded at
    # parse time, so putting it there would test nothing.
    with_comment = "<p>Conduction moves heat.</p><!-- note -->"
    without = "<p>Conduction moves heat.</p>"

    assert units_and_elements(with_comment)[1] == units_and_elements(without)[1]


def test_a_body_with_no_element_node_counts_zero_rather_than_crashing():
    """
    lxml's HTML parser returns no root at all for a document with no element
    node — a lone comment, DOCTYPE, PI or CDATA. Left unguarded that is an
    AttributeError from deep inside the extractor, which the command does not
    catch and a task reports as the translator's fault.
    """
    benchmark = benchmark_module.Benchmark(
        block_id=BLOCK_ID, display_name="x", content=BENCHMARK, units=frozenset({"a"})
    )

    for body in ("<!-- draft -->", "<!DOCTYPE html>", "<?xml version='1.0'?>", "   "):
        assert benchmark_module.units_and_elements(body) == ([], 0)
        assert benchmark_module.count_unchanged_units(body, benchmark) == 0


def test_a_body_with_no_element_node_counts_zero_inside_the_platform_too():
    """
    Bare lxml returns None for an element-free document; edx-platform does
    not have bare lxml.

    ``defuse_xml_libs()`` replaces ``lxml.etree`` with a wrapper whose
    ``fromstring`` calls ``.getroottree()`` on the result, so the same input
    raises where it used to return None. Both shapes mean "nothing to
    translate", and the host suite only ever sees the first — which is how
    this reached CI green and the platform broken.
    """
    benchmark = benchmark_module.Benchmark(
        block_id=BLOCK_ID, display_name="x", content=BENCHMARK, units=frozenset({"a"})
    )

    with mock.patch.object(
        HtmlXmlTranslationHelper,
        "parse",
        side_effect=AttributeError("'NoneType' object has no attribute 'getroottree'"),
    ):
        assert benchmark_module.units_and_elements("<!-- draft -->") == ([], 0)
        assert benchmark_module.count_unchanged_units("<!-- draft -->", benchmark) == 0

    # A bug in the extractor must still escape rather than read as zero.
    with (
        mock.patch.object(
            benchmark_module, "units_and_elements", side_effect=TypeError("broken")
        ),
        pytest.raises(TypeError, match="broken"),
    ):
        benchmark_module.count_unchanged_units("<p>x</p>", benchmark)


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_the_run_is_scored_on_the_content_it_pinned(benchmark_block):
    """
    The block is live content an author can publish over while the prompt
    waits. Re-reading after the run row exists means the command's units
    match the text the tasks will actually be given.
    """
    edited = BENCHMARK.replace("Conduction", "Convection")

    def edit_then_confirm(_prompt):
        benchmark_block.get_item.return_value = mock.Mock(
            data=edited, display_name="Heat Transfer"
        )
        return "y"

    with mock.patch("builtins.input", side_effect=edit_then_confirm):
        output, _ = _run(confirm=False, translators="openai", judges="openai")

    # The fake translator rewrites "Conduction", so against the edited text
    # that paragraph comes back untouched and counts as one unchanged unit.
    # Against the stale copy the command read before the prompt, it matches
    # nothing and the column reads 0.
    arm = next(
        line for line in output.splitlines() if line.startswith("openai/gpt-test →")
    )
    assert arm.split()[-1] == "1"


def test_benchmark_content_parses_into_units_and_elements():
    """The parser the command and every task share, on real benchmark content."""
    units, elements = units_and_elements(BENCHMARK)

    assert len(units) > 2  # noqa: PLR2004
    assert elements > 2  # noqa: PLR2004
    # The display_name attribute is translatable and must be picked up; the
    # exact value, since a substring check would also match the body text.
    assert "Heat Transfer" in units


def test_judging_calls_are_bounded_and_do_not_retry(judge):
    """
    A hung judge holds a worker slot, and the client retries twice by default.

    Scoring inherited the 300s provider default and the client's two retries,
    so one hang could occupy a slot for 15 minutes.
    """
    with mock.patch.object(
        llm_providers,
        "completion",
        return_value=_response(
            _wrapped(
                '{"accuracy": 8, "fluency": 8, "terminology": 8, "justification": "x"}'
            )
        ),
    ) as completion:
        judge.rate_translation(
            source_language="en",
            target_language="hi",
            source_content=SOURCE,
            translated_content=TRANSLATED,
        )

    assert completion.call_args.kwargs["timeout"] == llm_providers.SCORING_TIMEOUT
    assert completion.call_args.kwargs["max_retries"] == 0


def test_validation_keeps_its_defaults_unless_a_caller_overrides_them(judge):
    """translate_course must not inherit the benchmark's call parameters."""
    reply = _wrapped("<problem><p>ok</p></problem>")

    with mock.patch.object(
        llm_providers, "completion", return_value=_response(reply)
    ) as completion:
        judge.validate_translation(
            source_language="en",
            target_language="hi",
            source_content=SOURCE,
            translated_content=TRANSLATED,
        )
    assert completion.call_args.kwargs["timeout"] == llm_providers.VALIDATION_TIMEOUT
    assert "max_retries" not in completion.call_args.kwargs

    with mock.patch.object(
        llm_providers, "completion", return_value=_response(reply)
    ) as completion:
        judge.validate_translation(
            source_language="en",
            target_language="hi",
            source_content=SOURCE,
            translated_content=TRANSLATED,
            timeout=240,
            max_retries=0,
        )
    assert completion.call_args.kwargs["timeout"] == 240  # noqa: PLR2004
    assert completion.call_args.kwargs["max_retries"] == 0


# --------------------------------------------------------- celery plumbing


@pytest.mark.parametrize("task", BENCHMARK_TASKS)
def test_benchmark_tasks_stay_off_the_default_queue(task):
    """
    A run is hundreds of tasks on workers shared with course publishing.

    Anything that lands on the default queue blocks CMS work for the duration.
    """
    # The literal, not BENCHMARK_QUEUE: comparing the constant to itself is a
    # tautology that passes for any value, including Celery's own default.
    assert task.queue == "edx.cms.core.low"


@pytest.mark.parametrize("task", BENCHMARK_TASKS)
def test_benchmark_tasks_retry_only_transient_failures(task):
    """
    A malformed judge reply will be malformed again.

    Retrying it only delays the exclusion, so retries are limited to the
    classes that can plausibly succeed on a second attempt. The budget is
    asserted too: a retry_kwargs that quietly became zero reads, from the
    outside, exactly like the retries never being wired up at all.
    """
    assert set(task.autoretry_for) == {RateLimitError, Timeout}
    assert task.retry_kwargs["max_retries"] == 2  # noqa: PLR2004
    assert task.retry_backoff


@pytest.mark.usefixtures("benchmark_block")
@pytest.mark.parametrize("stage", list(BENCHMARK_STAGES))
@pytest.mark.parametrize("transient", [True, False])
def test_a_transient_failure_reaches_the_retry_wrapper(
    benchmark_arms, stage, transient
):
    """
    Celery's autoretry wrapper only sees what escapes the task body.

    A task that caught its own Timeout would make autoretry_for dead config
    while every assertion about that config still passed, so this drives each
    task body and asks whether the exception got out. Every stage is covered:
    the first time this was written it covered one, and the other three could
    have their re-raise deleted with the suite still green.
    """
    arm, source = benchmark_arms
    invoke, transient_mode, fatal_mode = BENCHMARK_STAGES[stage]
    mode = transient_mode if transient else fatal_mode

    with mock.patch(
        "ol_openedx_course_translations.tasks.get_translation_provider",
        lambda *spec: FakeProvider("/".join(spec), mode=mode),
    ):
        if transient:
            # Called directly, Task.retry re-raises rather than rescheduling.
            with pytest.raises(Timeout):
                invoke(arm, source)
            arm.refresh_from_db()
            assert arm.error == ""
        else:
            assert invoke(arm, source)["status"] == "error"


@pytest.mark.django_db
@pytest.mark.usefixtures("benchmark_block")
def test_the_benchmark_sets_its_own_validation_timeout(benchmark_arms):
    """
    The task, not the provider, is what opts out of the client's retries.

    Deleting the override at the call site leaves the provider's own defaults
    in place — a 90s cap with two silent retries — which is the behaviour the
    benchmark changed on purpose.
    """
    arm, source = benchmark_arms
    recorded = {}

    class RecordingProvider(FakeProvider):
        def validate_translation(self, **kwargs):
            recorded.update(kwargs)
            return super().validate_translation(**kwargs)

    with mock.patch(
        "ol_openedx_course_translations.tasks.get_translation_provider",
        lambda *spec: RecordingProvider("/".join(spec)),
    ):
        tasks.benchmark_validate_task(arm.pk, source.pk, SPEC, "hi", source.run.pk)

    assert recorded["timeout"] == tasks.BENCHMARK_VALIDATION_TIMEOUT
    assert recorded["max_retries"] == llm_providers.NO_CLIENT_RETRIES
    # The override is only worth making if it is longer than the default it
    # replaces, which is the whole reason the constant exists.
    assert tasks.BENCHMARK_VALIDATION_TIMEOUT > llm_providers.VALIDATION_TIMEOUT


class _StubGroupResult:
    """A group result whose readiness and payload the test decides."""

    def __init__(self, *, ready_after=0, payload=()):
        self._polls_left = ready_after
        self._payload = list(payload)
        self.results = []
        self.revoked = False
        self.get_kwargs = None

    def ready(self):
        # Becomes ready eventually, so a deadline that stopped working fails
        # the test rather than hanging it.
        if self._polls_left <= 0:
            return True
        self._polls_left -= 1
        return False

    def revoke(self):
        self.revoked = True

    def get(self, **kwargs):
        self.get_kwargs = kwargs
        return self._payload


def _dispatch_against(stub, monkeypatch, timeout=None):
    monkeypatch.setattr(
        benchmark_command,
        "group",
        lambda _signatures: mock.Mock(apply_async=lambda: stub),
    )
    monkeypatch.setattr(benchmark_command, "BENCHMARK_POLL_INTERVAL", 0)
    if timeout is not None:
        monkeypatch.setattr(benchmark_command, "BENCHMARK_STAGE_TIMEOUT", timeout)
    command = benchmark_command.Command()
    command.stdout = mock.Mock()
    return command._dispatch([mock.Mock()], "Scoring")  # noqa: SLF001


def test_a_stage_that_never_finishes_ends_the_run_instead_of_hanging(monkeypatch):
    """
    A child lost with its worker never becomes ready.

    Without the deadline the command spins forever on a run nobody is reading,
    and the remaining tasks keep spending. Every other test runs eager, so the
    polling loop is only reachable from here.
    """
    stub = _StubGroupResult(ready_after=5, payload=[{"status": "success"}])

    with pytest.raises(CommandError, match="Scoring did not finish within"):
        _dispatch_against(stub, monkeypatch, timeout=-1)

    assert stub.revoked


def test_one_dead_task_does_not_take_down_its_stage(monkeypatch):
    """
    Collected with propagate=False.

    A task that raised comes back as the exception object to record, rather
    than an exception that costs the stage the work already paid for.
    """
    died = RuntimeError("worker died")
    stub = _StubGroupResult(payload=[{"status": "success"}, died])

    results = _dispatch_against(stub, monkeypatch)

    assert stub.get_kwargs["propagate"] is False
    assert results[1] is died
    assert benchmark_command.Command._outcome(died) == (  # noqa: SLF001
        False,
        "RuntimeError: worker died",
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_an_interrupted_run_is_not_marked_complete():
    """
    Arms are written as their tasks finish.

    Without the marker a run abandoned halfway looks exactly like one that
    finished, in the very table that is meant to stay comparable over time.
    """
    _run(translators="openai", judges="openai")
    assert TranslationQualityRun.objects.get().completed_at is not None

    with pytest.raises(CommandError):
        _run(
            modes={"openai/gpt-test": "score_rejects"},
            translators="openai",
            judges="openai",
        )
    abandoned = TranslationQualityRun.objects.latest("pk")
    assert abandoned.completed_at is None
    assert "incomplete" in str(abandoned)


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_only_the_shortlist_reaches_the_comparative_pass(settings):
    """
    The second pass exists so the whole field is not put in one call.

    Every other command test uses at most six candidates, where bypassing the
    shortlist entirely would change nothing observable.
    """
    settings.TRANSLATIONS_PROVIDERS["mistral"]["api_key"] = FAKE_KEY
    sent = []
    original = FakeProvider.rank_translations

    def record(self, *, candidates, **kwargs):
        sent.append(candidates)
        return original(self, candidates=candidates, **kwargs)

    with mock.patch.object(FakeProvider, "rank_translations", record):
        _run(translators="openai,gemini,mistral", judges="openai")

    assert TranslationQualityCandidate.objects.count() == 9  # noqa: PLR2004
    assert sent
    assert all(len(labels) <= SHORTLIST_CAP for labels in sent)


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_each_judge_gets_its_own_shuffle():
    """
    Shuffling once per run would leave every judge the same running order.

    Deleting the shuffle is invisible to a bijectivity check, so this asserts
    the per-judge call itself.
    """
    with mock.patch.object(
        benchmark_command.random, "shuffle", wraps=random.shuffle
    ) as shuffle:
        _run(translators="openai,gemini", judges="openai,gemini")

    assert shuffle.call_count == 2  # noqa: PLR2004


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_comparative_only_skips_scoring_and_still_names_a_winner():
    """
    One comparative call per judge, no per-candidate scoring.

    The saving is the whole point of the flag: scoring is candidates x judges
    calls and ranking is one per judge, so the score rows must be absent and
    a verdict must still appear.
    """
    # One judge, so its four ranks are distinct and the verdict cannot tie.
    output, _ = _run(
        translators="openai,gemini", judges="openai", comparative_only=True
    )

    scores = TranslationQualityScore.objects.all()
    assert scores.count() == 4  # 4 candidates x 1 judge  # noqa: PLR2004
    # Ranked, never scored.
    assert all(score.accuracy is None for score in scores)
    assert all(score.comparative_rank is not None for score in scores)
    assert "Winner:" in output
    assert "mean score" in output  # the column stays, rendered as an em dash
    assert "—" in output
    # The table is read differently in this mode, so it says so beneath.
    assert "the scoring pass was skipped" in output


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_comparative_only_declines_a_tied_lead():
    """
    One pass has no second signal to break a tie, so it says so.

    Both the shuffle and the ranks are pinned here: leaving either to chance
    makes the tie appear only on some runs, and a verdict test that passes
    intermittently is worse than none.
    """

    def tied(_self, *, candidates, **_kwargs):
        # Two candidates share first place; the rest follow in label order.
        return {
            label: 1 if index <= 2 else index  # noqa: PLR2004
            for index, label in enumerate(sorted(candidates), start=1)
        }

    with (
        mock.patch.object(benchmark_command.random, "shuffle", return_value=None),
        mock.patch.object(FakeProvider, "rank_translations", tied),
    ):
        output, _ = _run(
            translators="openai,gemini", judges="openai,gemini", comparative_only=True
        )

    assert "No clear winner" in output
    assert "tied" in output


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_comparative_only_ranks_every_candidate_not_a_shortlist():
    """Without scores there is no mean rank to shortlist by, so all of them go."""
    sent = []
    original = FakeProvider.rank_translations

    def record(self, *, candidates, **kwargs):
        sent.append(sorted(candidates))
        return original(self, candidates=candidates, **kwargs)

    with mock.patch.object(FakeProvider, "rank_translations", record):
        _run(translators="openai,gemini", judges="openai", comparative_only=True)

    assert sent == [["A", "B", "C", "D"]]


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_comparative_only_refuses_more_candidates_than_labels(settings):
    """
    Beyond the alphabet the label zip would truncate in silence.

    Refusing in the preflight is the difference between being told the roster
    is too wide and quietly ranking a subset of it.
    """
    settings.TRANSLATIONS_PROVIDERS.update(
        {f"p{index}": {"api_key": FAKE_KEY, "default_model": "m"} for index in range(6)}
    )
    roster = ",".join(f"p{index}/m" for index in range(6))

    with pytest.raises(CommandError, match="anonymous labels"):
        _run(translators=roster, judges="openai", comparative_only=True)

    assert not TranslationQualityRun.objects.exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_the_admin_renders_a_comparative_only_run():
    """
    Those runs store ranks with null criteria. Averaging them raises, so the
    admin page of a run made with --comparative-only was unopenable — the
    mode and the page that displays it disagreed.
    """
    _run(translators="openai,gemini", judges="openai", comparative_only=True)
    run = TranslationQualityRun.objects.get()

    # The run records which passes it ran; the page reads that rather than
    # guessing from the absence of scores.
    assert run.comparative_only

    html = TranslationQualityRunAdmin(TranslationQualityRun, mock.Mock()).report(run)

    assert "Verdict:" in html
    # Whole cell, not a fragment: the missing scores must read as an em dash,
    # and the position must be the rank rather than a second statistic.
    assert "<td>1.0 · — · #1</td>" in html
    # The two-pass legend describes a shortlist and scores this run has not.
    assert "ranked comparatively only" in html

    inline = TranslationQualityCandidateInline(TranslationQualityCandidate, admin.site)
    for candidate in run.candidates.all():
        # The same null criteria reach the inline on the same page, where
        # they used to render as "None/None/None".
        assert "None" not in inline.judge_scores(candidate)


def test_the_run_admin_is_read_only_but_a_run_can_be_deleted():
    """
    A run can be removed as a whole, never altered.

    Smoke tests and interrupted runs need to be cleared out somehow. Deleting
    one candidate would quietly change the standings, so the inline still can't.
    """
    admin_view = TranslationQualityRunAdmin(TranslationQualityRun, admin.site)
    inline = TranslationQualityCandidateInline(TranslationQualityCandidate, admin.site)
    opts = TranslationQualityRun._meta  # noqa: SLF001
    delete_perm = f"{opts.app_label}.{get_permission_codename('delete', opts)}"
    request = mock.Mock()
    request.user.has_perm = lambda perm: perm == delete_perm

    assert not admin_view.has_add_permission(request)
    assert not admin_view.has_change_permission(request)
    assert admin_view.has_delete_permission(request)
    assert not inline.can_delete

    request.user.has_perm = lambda perm: False  # noqa: ARG005
    assert not admin_view.has_delete_permission(request)


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_each_arm_stores_the_content_it_was_scored_on():
    """
    Tasks address rows by id, so the content has to be on the row.

    It is also what lets a reader check a judge's verdict against the text.
    """
    _run(translators="openai", judges="openai")

    # The unvalidated arm held the translation the validators read, and is
    # gone once they have: only validated pairings are under test.
    assert not TranslationQualityCandidate.objects.filter(validator="").exists()

    validated = TranslationQualityCandidate.objects.get()
    # The validator's edit is visible, so the stored arm is its output and not
    # a copy of the translation it was given.
    assert "CONDUCCION!" in validated.translated_content


def _stored_run():
    """A run row to hang hand-built candidates and scores on."""
    return TranslationQualityRun.objects.create(
        target_language="hi",
        benchmark_block_id=BLOCK_ID,
        translators_arg="",
        judges_arg="",
    )


@pytest.mark.django_db
def test_the_standings_render_a_partly_judged_run():
    """
    Partial coverage is the designed-for case and the one that broke.

    The admin aggregates whatever rows are stored, so a judge can be missing
    a candidate (its task failed) and a candidate can be scored but never
    shortlisted. Both produce a cell the two-pass shape does not describe.
    """
    run = _stored_run()
    rows = {
        name: TranslationQualityCandidate.objects.create(
            run=run, translator=name, validator="v"
        )
        for name in ("a", "b", "c")
    }
    # Written first, sorts last: column order must not follow insertion.
    # This judge scored all three and ranked only the leader. Its criteria
    # differ from each other, so the order they render in is observable.
    for name, (score, rank) in {"a": (9, 1), "b": (7, None), "c": (6, None)}.items():
        TranslationQualityScore.objects.create(
            candidate=rows[name],
            judge="zeta",
            accuracy=score,
            fluency=score - 2,
            terminology=score - 3,
            comparative_rank=rank,
        )
    # The other scored two of them and ranked none.
    for name in ("a", "b"):
        TranslationQualityScore.objects.create(
            candidate=rows[name], judge="alpha", accuracy=8, fluency=8, terminology=8
        )

    html = TranslationQualityRunAdmin(TranslationQualityRun, mock.Mock()).report(run)

    # Rendered accuracy/fluency/terminology, the order the legend promises.
    assert "9/7/6" in html
    # A judge that scored but never ranked still gets its column.
    assert "<th>alpha</th>" in html
    assert html.index("<th>alpha</th>") < html.index("<th>zeta</th>")
    # alpha never placed c, and formatting a missing position raised.
    assert "<td>—</td>" in html
    # b and c were not shortlisted, so they carry no rank at all.
    assert "#None" not in html


@pytest.mark.django_db
def test_a_run_with_candidates_and_no_scores_says_so():
    """The state an operator opens the admin to diagnose: a run that died."""
    run = _stored_run()
    TranslationQualityCandidate.objects.create(run=run, translator="a", validator="v")

    report = TranslationQualityRunAdmin(TranslationQualityRun, mock.Mock()).report(run)

    assert report == "No scores recorded."


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_comparative_only_ranks_no_failed_arm():
    """
    Its contenders are every *usable* arm, not every arm.

    A failed arm has no content, so ranking it asks a judge to compare blank
    text against real translations.
    """
    _run(
        translators="openai,gemini",
        judges="openai",
        comparative_only=True,
        modes={WINNER: "translate_raises"},
    )

    failed = TranslationQualityCandidate.objects.exclude(error="")
    assert failed.exists()
    assert not TranslationQualityScore.objects.filter(candidate__in=failed).exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_comparative_only_refuses_when_no_judge_ranked():
    """
    Its only pass failing leaves nothing to report.

    Without the refusal the standings are built from an empty list, and the
    operator gets a ValueError out of the formatter instead of the reason.
    """
    with pytest.raises(CommandError, match="No candidate was ranked"):
        _run(
            translators="openai,gemini",
            judges="openai",
            comparative_only=True,
            modes={WINNER: "rank_rejects"},
        )


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_a_single_contender_is_not_sent_to_be_ranked():
    """Ranking a field of one buys nothing and costs a call per judge."""
    output, _ = _run(translators="openai", judges="openai")

    stages = [stage for p in FakeProvider.all_providers for stage, _ in p.calls]
    assert "score" in stages
    assert "rank" not in stages
    # And the report says so rather than reporting a pass of nobody.
    assert "First-place votes" not in output
    assert "Comparative pass skipped" in output


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_comparative_only_refuses_one_translator_before_spending():
    """With scoring skipped, a field of one has no result to give."""
    with pytest.raises(CommandError, match="nothing to compare"):
        _run(translators="openai", judges="openai", comparative_only=True)

    assert not FakeProvider.all_providers
    assert not TranslationQualityRun.objects.exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_comparative_only_with_no_usable_arm_blames_the_arms_not_the_judges():
    modes = {
        "openai/gpt-test": "translate_raises",
        "gemini/gemini-test": "translate_raises",
    }
    with pytest.raises(CommandError, match="Only 0 usable candidate"):
        _run(modes, judges="openai", comparative_only=True)

    stages = [stage for p in FakeProvider.all_providers for stage, _ in p.calls]
    assert "rank" not in stages


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
@pytest.mark.parametrize(
    ("mode", "message"),
    [
        ("translate_empty", "provider returned nothing"),
        ("translate_untranslatable", "no translatable units"),
    ],
)
def test_a_translator_that_returned_nothing_usable_says_which(mode, message):
    """
    Each gate names its own failure.

    Both fall through to the same arm rejection, so the recorded reason
    is the only thing that tells them apart — and it is what the run reports
    back to the operator.
    """
    with pytest.raises(CommandError):
        _run(translators="openai", judges="openai", modes={WINNER: mode})

    errors = {c.error for c in TranslationQualityCandidate.objects.all()}
    assert errors
    assert all(message in error for error in errors)


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_a_validator_that_dies_outside_its_handler_records_why():
    """
    As for a translator: the task writes its own failures, but one that never
    reached its handler leaves the row blank, and the arm is then reported as
    having neither content nor a reason.

    Driven at the task's own read rather than through the modulestore: in
    one process the second stage reuses the cached block and never
    re-reads, so patching the helper stands in for a cold worker that
    does.
    """
    with (
        # An exception instance in an iterable side_effect is raised rather
        # than returned, so the translate task reads the block and the
        # validate task's read fails. Exactly two entries: the unusable arm
        # aborts the run before the scoring pass asks for a third.
        mock.patch(
            "ol_openedx_course_translations.tasks.cached_benchmark",
            side_effect=[BENCHMARK_BLOCK, RuntimeError("worker went away")],
        ),
        pytest.raises(CommandError),
    ):
        _run(translators="openai", judges="openai")

    arm = TranslationQualityCandidate.objects.get(validator=WINNER)
    assert "worker went away" in arm.error


@pytest.mark.django_db
@pytest.mark.usefixtures("benchmark_block")
def test_an_arm_with_neither_content_nor_error_is_not_scored():
    """
    An empty string is not a translation.

    A row no task ever wrote to is empty on both fields, and treating that
    content as present would send blank text to the judges as a candidate.
    """
    run = _stored_run()
    TranslationQualityCandidate.objects.create(run=run, translator="a", validator="b")

    arms = benchmark_command.Command()._load_arms(run, BENCHMARK_BLOCK)  # noqa: SLF001

    assert not any(arm.usable for arm in arms.values())


def test_the_label_limit_applies_only_to_comparative_only():
    """
    Two-pass runs never put the whole field in one call.

    Their comparative pass sees the shortlist, so the 26-label ceiling is a
    property of the flag, not of the candidate count.
    """

    benchmark_command.Command()._confirm_run(  # noqa: SLF001
        translators=[f"p{index}/m" for index in range(6)],
        judges=["openai/gpt-test"],
        benchmark=BENCHMARK_BLOCK,
        skip_prompt=True,
        comparative_only=False,
    )


@pytest.mark.django_db
def test_a_run_whose_judges_never_ranked_names_no_winner():
    """
    The verdict is the comparative pass's, so scores alone do not crown one.

    Without the fallback the line renders empty and reads as a winner whose
    name failed to load.
    """
    run = _stored_run()
    candidate = TranslationQualityCandidate.objects.create(
        run=run, translator="a", validator=""
    )
    TranslationQualityScore.objects.create(
        candidate=candidate, judge="j1", accuracy=9, fluency=9, terminology=9
    )
    inline = TranslationQualityCandidateInline(TranslationQualityCandidate, admin.site)

    html = TranslationQualityRunAdmin(TranslationQualityRun, mock.Mock()).report(run)

    assert "no clear winner" in html
    # A run made before validated-only candidates still has to read.
    assert inline.validator_display(candidate) == "none"


@pytest.mark.django_db
def test_a_candidate_no_judge_reached_renders_as_a_dash():
    """A blank cell would read as a score of nothing rather than no score."""
    run = _stored_run()
    candidate = TranslationQualityCandidate.objects.create(
        run=run, translator="a", validator="v"
    )
    inline = TranslationQualityCandidateInline(TranslationQualityCandidate, admin.site)

    assert inline.judge_scores(candidate) == "—"


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers")
def test_the_block_is_read_once_however_many_tasks_run(benchmark_block):
    """
    Every task needs the same block, and each read decodes a whole course
    structure on a queue shared with course publishing.

    The command still reads twice itself — once before the run is created
    and once after, to close the confirmation-prompt window — so only the
    tasks' reads collapse.

    Two translators, deliberately: with one, ``_rank`` returns before
    dispatching and the rank stage stops being covered here at all.
    """
    _run(translators="openai,gemini", judges="openai")

    command_reads = 2
    assert benchmark_block.get_item.call_count == command_reads + 1


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers")
def test_a_later_run_does_not_reuse_an_earlier_run_s_block(benchmark_block):
    """
    A Celery child outlives a run, so a cache keyed on the block alone would
    serve a run in the afternoon the copy it read that morning — and the
    standings would look ordinary while measuring content the course no
    longer has.
    """
    _run(translators="openai", judges="openai")
    first_run_reads = benchmark_block.get_item.call_count

    _run(translators="openai", judges="openai")

    assert benchmark_block.get_item.call_count == 2 * first_run_reads


@pytest.mark.django_db
def test_a_run_with_only_ranks_still_renders_its_standings():
    """
    The flag says what the run set out to do; the rows say what it got.

    When they disagree the page must show what is stored rather than assert
    that a run which cost real spend recorded nothing.
    """
    run = _stored_run()
    for name, rank in (("a", 1), ("b", 2)):
        TranslationQualityScore.objects.create(
            candidate=TranslationQualityCandidate.objects.create(
                run=run, translator=name, validator="v"
            ),
            judge="j1",
            comparative_rank=rank,
        )

    html = TranslationQualityRunAdmin(TranslationQualityRun, mock.Mock()).report(run)

    assert "No scores recorded." not in html
    assert "<th>j1</th>" in html


@pytest.mark.django_db
def test_the_standings_do_not_query_once_per_candidate(django_assert_num_queries):
    """
    The report reads every candidate's scores, so without the prefetch the
    page costs a query per row — and the comment saying so is not a check.
    """
    run = _stored_run()
    for name in ("a", "b", "c"):
        TranslationQualityScore.objects.create(
            candidate=TranslationQualityCandidate.objects.create(
                run=run, translator=name, validator="v"
            ),
            judge="j1",
            accuracy=8,
            fluency=8,
            terminology=8,
        )

    with django_assert_num_queries(2):
        TranslationQualityRunAdmin(TranslationQualityRun, mock.Mock()).report(run)


@pytest.mark.django_db
def test_a_half_scored_row_is_read_the_same_way_everywhere():
    """
    The command writes all three criteria or none, so this row can only come
    from a hand edit or a restored dump. Both readers must still agree: one
    treating it as scored and the other not is how a row renders in the
    inline and vanishes from the standings without a word.
    """
    run = _stored_run()
    candidate = TranslationQualityCandidate.objects.create(
        run=run, translator="a", validator="v"
    )
    TranslationQualityScore.objects.create(
        candidate=candidate, judge="j1", accuracy=7, comparative_rank=1
    )
    inline = TranslationQualityCandidateInline(TranslationQualityCandidate, admin.site)

    html = TranslationQualityRunAdmin(TranslationQualityRun, mock.Mock()).report(run)

    # Pinned exactly rather than by absence of "None". The inline goes
    # through _criteria; the standings fall back to the ratings default,
    # since a half-scored row is never recorded there. Two paths to the
    # same em dash, so both are asserted.
    assert inline.judge_scores(candidate) == "j1 — [#1]"
    assert "<td>1.0 · — · #1</td>" in html
    # Present in the standings, not merely absent from the failure text.
    assert "a → v" in html


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_a_total_ranking_failure_is_reported_as_none_of_the_judges():
    """
    Every ranking judge failing must not read like a tie.

    The verdict says only that no candidate was ranked, which is also what
    it says when there was nothing to rank; the count is what separates them.
    """
    output, _ = _run(
        modes={WINNER: "rank_rejects", "gemini/gemini-test": "rank_rejects"},
        translators="openai,gemini",
        judges="openai,gemini",
    )

    assert "First-place votes among the contenders (0 of 2 judge(s) ranked)" in output
    # And says so, rather than leaving the header over an empty list.
    assert "no judge named a single best candidate" in output


@pytest.mark.django_db
def test_stored_scores_are_rendered_whatever_the_run_s_mode_says():
    """
    The page renders evidence, not intent.

    A run flagged comparative-only whose rows carry criteria — a restored
    dump, a mode changed after the fact — must show those scores rather
    than a comparative table that hides them.
    """
    run = _stored_run()
    run.comparative_only = True
    run.save(update_fields=["comparative_only"])
    for name, score, rank in (("a", 9, 2), ("b", 5, 1)):
        TranslationQualityScore.objects.create(
            candidate=TranslationQualityCandidate.objects.create(
                run=run, translator=name, validator="v"
            ),
            judge="j1",
            accuracy=score,
            fluency=score,
            terminology=score,
            comparative_rank=rank,
        )

    html = TranslationQualityRunAdmin(TranslationQualityRun, mock.Mock()).report(run)

    assert "9.00" in html
    # Ordered by the scores, not by the comparative ranks: a leads the table
    # while b, ranked first head to head, still takes the verdict.
    assert "<td>1</td><td>a → v</td>" in html
    assert "Verdict:</b> b → v" in html


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_a_task_will_not_write_to_a_row_from_another_run():
    """
    The run id is the cache key, but it is also authority.

    Dispatch always pairs a row with its own run, so this guards a
    mismatched pair: a replayed call, a hand-invoked one, or a label map
    built from ids that are no longer this run's. Writing such an arm would
    change a finished run's stored content without touching its standings.
    """
    owning_run, other_run = _stored_run(), _stored_run()
    candidate = TranslationQualityCandidate.objects.create(
        run=owning_run, translator="a", validator="", translated_content=BENCHMARK
    )
    native = TranslationQualityCandidate.objects.create(
        run=other_run, translator="a", validator="", translated_content=BENCHMARK
    )

    with pytest.raises(TranslationQualityCandidate.DoesNotExist):
        tasks.benchmark_translate_task(candidate.pk, SPEC, "hi", other_run.pk)

    # Both of the validate task's rows are scoped, and each is separately
    # able to be the foreign one.
    with pytest.raises(TranslationQualityCandidate.DoesNotExist):
        tasks.benchmark_validate_task(candidate.pk, native.pk, SPEC, "hi", other_run.pk)
    with pytest.raises(TranslationQualityCandidate.DoesNotExist):
        tasks.benchmark_validate_task(native.pk, candidate.pk, SPEC, "hi", other_run.pk)

    # The scoring task looks its row up inside its handler, so it reports
    # rather than raises — but it must still not read another run's arm.
    scored = tasks.benchmark_score_task(candidate.pk, SPEC, "hi", other_run.pk)

    assert scored["status"] == "error"
    assert "DoesNotExist" in scored["error"]

    # The ranking task resolves a whole label map, so it filters rather than
    # fetching, and an unscoped filter would rank another run's arms. The
    # provider is faked, so reaching it at all would mean a success here.
    with mock.patch(
        "ol_openedx_course_translations.tasks.get_translation_provider",
        lambda *spec: FakeProvider("/".join(spec)),
    ):
        ranked = tasks.benchmark_rank_task(
            SPEC, {"A": candidate.pk}, "hi", other_run.pk
        )

    assert ranked["status"] == "error"
    assert f"are not in run {other_run.pk}" in ranked["error"]


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers")
def test_each_run_is_benchmarked_on_the_block_it_names():
    """
    The cache resolves the block through the run, so reading the wrong run
    would benchmark the wrong course content while every id on the page
    still looked right.
    """
    other_id = BLOCK_ID.replace("benchmark1", "benchmark2")
    blocks = {
        BLOCK_ID: mock.Mock(data=BENCHMARK, display_name="Heat Transfer"),
        other_id: mock.Mock(
            data="<p>Radiation needs no medium at all.</p>", display_name="Radiation"
        ),
    }
    store = mock.Mock()
    store.get_item.side_effect = lambda key, **_kwargs: blocks[str(key)]

    with mock.patch("xmodule.modulestore.django.modulestore", return_value=store):
        _run(translators="openai", judges="openai")
        _run(translators="openai", judges="openai", benchmark_block=other_id)

    second = TranslationQualityRun.objects.order_by("-pk").first()
    assert second.benchmark_block_id == other_id
    sources = {
        kwargs["source_content"]
        for provider in FakeProvider.all_providers
        for stage, kwargs in provider.calls
        if stage == "score"
    }
    assert any("Conduction" in source for source in sources)
    assert any("Conduction" not in source for source in sources)


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_a_ranking_failure_is_recorded_on_the_run():
    """
    A console warning is gone by the time anyone opens the standings and
    wonders why nothing carries a rank.

    The scoring pass already records why a judge dropped out; the
    comparative pass has to as well, or a run that scored everything and
    ranked nothing looks like a run where ranking was never tried.
    """
    _run(
        modes={"gemini/gemini-test": "rank_rejects"},
        translators="openai,gemini",
        judges="openai,gemini",
    )

    stored = TranslationQualityRun.objects.get().excluded_judges

    assert "gemini/gemini-test: ranking:" in stored
    assert "unparseable ranking" in stored


@pytest.mark.django_db
def test_a_judge_that_only_ranked_still_gets_a_column():
    """
    The verdict comes from the comparative pass, so a judge that ranked
    without scoring decided it. Choosing the scoring judges over the
    ranking ones would name a winner no column on the page accounts for.
    """
    run = _stored_run()
    candidate = TranslationQualityCandidate.objects.create(
        run=run, translator="a", validator="v"
    )
    TranslationQualityScore.objects.create(
        candidate=candidate, judge="scorer", accuracy=8, fluency=8, terminology=8
    )
    TranslationQualityScore.objects.create(
        candidate=candidate, judge="ranker", comparative_rank=1
    )

    html = TranslationQualityRunAdmin(TranslationQualityRun, mock.Mock()).report(run)

    assert "<th>scorer</th>" in html
    assert "<th>ranker</th>" in html


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_a_block_that_goes_missing_mid_run_keeps_what_the_run_produced():
    """
    The block cache is per worker process per run, so one worker finding the
    block gone is not the whole run's verdict.

    Aborting there would discard a scoring pass already paid for — hundreds
    of provider calls — which is what the report-before-persist ordering
    exists to avoid. Only the translate stage, which has paid for nothing,
    still aborts.
    """
    # translate, validate, then one judge's cold worker finds it gone.
    reads = [
        BENCHMARK_BLOCK,
        BENCHMARK_BLOCK,
        BenchmarkError("No published block at gone"),
        BENCHMARK_BLOCK,
    ]

    with mock.patch(
        "ol_openedx_course_translations.tasks.cached_benchmark", side_effect=reads
    ):
        output, _ = _run(translators="openai", judges="openai,gemini")

    assert "mean rank" in output
    stored = TranslationQualityRun.objects.get()
    assert TranslationQualityScore.objects.exists()
    # Named as the block's fault, not the judge's: the reason can only be
    # keyed by the judge that hit it, so it has to say so itself.
    assert "benchmark unreadable: No published block at gone" in stored.excluded_judges
    assert "BenchmarkError" not in stored.excluded_judges


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_every_judge_failing_to_rank_is_recorded_before_the_run_gives_up():
    """
    The path that refuses the run never reaches _persist_scores, so it is
    the only chance to store why.

    This is the case the field was added for: a comparative-only run that
    ranked nothing otherwise stores no hint of what was attempted.
    """
    with pytest.raises(CommandError, match="No candidate was ranked"):
        _run(
            modes={WINNER: "rank_rejects", "gemini/gemini-test": "rank_rejects"},
            translators="openai,gemini",
            judges="openai,gemini",
            comparative_only=True,
        )

    stored = TranslationQualityRun.objects.get().excluded_judges

    assert stored.count("ranking:") == 2  # noqa: PLR2004
    assert "unparseable ranking" in stored


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_two_ranking_failures_are_one_stable_line_each():
    """
    The field is read by a human months later, so line-per-judge and a
    stable order are the contract.
    """
    _run(
        modes={WINNER: "rank_rejects", "gemini/gemini-test": "rank_rejects"},
        translators="openai,gemini",
        judges="openai,gemini",
    )

    stored = TranslationQualityRun.objects.get().excluded_judges

    assert stored.splitlines() == [
        "gemini/gemini-test: ranking: ValueError: unparseable ranking",
        "openai/gpt-test: ranking: ValueError: unparseable ranking",
    ]


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers")
def test_a_run_that_lost_its_row_says_which_run():
    """
    Django's own DoesNotExist names neither the run nor anything actionable,
    and the failure would otherwise be recorded as the judge's.
    """
    with pytest.raises(BenchmarkError, match="Run 999 has no row"):
        tasks.cached_benchmark(999)


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_an_overall_is_the_mean_of_a_judge_s_criteria():
    """
    Mean, not max: the ADR's ordering statistic. A max would let one
    generous criterion carry a candidate.
    """
    output, _ = _run(translators="openai", judges="openai")

    score = TranslationQualityScore.objects.get()
    run = TranslationQualityRun.objects.get()
    criteria = (score.accuracy, score.fluency, score.terminology)

    html = TranslationQualityRunAdmin(TranslationQualityRun, mock.Mock()).report(run)

    assert len(set(criteria)) > 1, "criteria must differ for this to discriminate"
    # Both readers collapse the criteria, and both have to agree with the
    # stored row: the console from the ratings, the page from the columns.
    assert f"{fmean(criteria):.2f}" in output
    assert f"<td>{fmean(criteria):.2f}</td>" in html


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_one_cold_worker_at_the_validate_stage_does_not_end_the_run():
    """
    By the validate stage the translations are paid for.

    The read fails before any provider call, so continuing costs nothing:
    that worker's arm fails free and the others survive to be scored.
    """
    calls = itertools.count()

    gone = BenchmarkError("No published block at gone")

    def read(_run_id):
        if next(calls) == 2:  # noqa: PLR2004 — the first validate task
            raise gone
        return BENCHMARK_BLOCK

    with mock.patch(
        "ol_openedx_course_translations.tasks.cached_benchmark", side_effect=read
    ):
        output, _ = _run(translators="openai,gemini", judges="openai")

    assert "mean rank" in output
    assert TranslationQualityScore.objects.exists()
    # The arm that hit it says so, and the rest were scored.
    assert TranslationQualityCandidate.objects.filter(
        error__contains="No published block at gone"
    ).exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_exclusions_from_both_passes_are_one_sorted_list():
    """
    The two passes contribute separate maps, and a union of two sorted maps
    is not itself sorted.

    Here the ranking failure sorts before the scoring exclusion, so merging
    without sorting would store them in pass order instead of judge order.
    """
    _run(
        modes={WINNER: "score_rejects", "gemini/gemini-test": "rank_rejects"},
        translators="openai,gemini",
        judges="openai,gemini",
    )

    stored = TranslationQualityRun.objects.get().excluded_judges

    assert stored.splitlines() == [
        "gemini/gemini-test: ranking: ValueError: unparseable ranking",
        "openai/gpt-test: ValueError: unparseable",
    ]


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "benchmark_block")
def test_a_judge_failing_on_several_arms_stores_the_same_reason_every_run():
    """
    Only the first failure per judge is kept, so which arm that is decides
    the stored text.

    Taken from the sorted candidate order rather than from whatever order
    the arms were read in, so two identical runs cannot store different
    reasons for the same failure.
    """
    with pytest.raises(CommandError, match="No candidate was scored"):
        _run(
            modes={"gemini/gemini-test": "score_rejects_per_arm"},
            translators="openai,gemini",
            judges="gemini",
        )

    stored = TranslationQualityRun.objects.get().excluded_judges

    # gemini → gemini sorts first, so its arm's text is the one kept.
    assert "CALOR[gemini/gemini-test]" in stored
    assert "CALOR[openai/gpt-test]" not in stored
