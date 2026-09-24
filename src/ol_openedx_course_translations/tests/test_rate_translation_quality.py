"""
Tests for the translation quality benchmark.

Three layers are covered: how a judge's reply is parsed, how scores are
aggregated into an ordering, and whether the command wires those together and
stores the result.
"""

from unittest import mock

import pytest
from django.core.management import call_command
from litellm import BadRequestError
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
from ol_openedx_course_translations.utils.quality_report import (
    CandidateRow,
    build_rows,
    pick_winner,
    select_shortlist,
)

FAKE_KEY = "not-a-real-key"  # pragma: allowlist secret
SOURCE = "<problem><p>Hello</p></problem>"
TRANSLATED = "<problem><p>नमस्ते</p></problem>"


@pytest.fixture(autouse=True)
def _clear_temperature_cache():
    llm_providers._MODEL_TEMPERATURES.clear()  # noqa: SLF001
    yield
    llm_providers._MODEL_TEMPERATURES.clear()  # noqa: SLF001


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


# ------------------------------------------------------------------ parsing


def test_scores_are_read_from_a_well_formed_reply(judge):
    result = _rate(
        judge,
        _wrapped(
            '{"accuracy": 8, "fluency": 7, "terminology": 9, "justification": "ok"}'
        ),
    )

    assert result["error"] is None
    assert result["scores"] == {"accuracy": 8, "fluency": 7, "terminology": 9}
    assert result["justification"] == "ok"


def test_scores_survive_a_fenced_and_chatty_reply(judge):
    """Models add prose and code fences whatever the prompt says."""
    reply = (
        "Sure! Here is my assessment:\n"
        "```json\n"
        '{"accuracy": 6, "fluency": 5, "terminology": 7, "justification": "fine"}\n'
        "```\n"
        "Let me know if you need more detail."
    )

    result = _rate(judge, reply)

    assert result["error"] is None
    assert result["scores"]["accuracy"] == 6  # noqa: PLR2004


def test_an_unparseable_reply_is_flagged_rather_than_raised(judge):
    result = _rate(judge, "I would rather not score this one.")

    assert result["scores"] == {}
    assert "no JSON object" in result["error"]


@pytest.mark.parametrize("value", [11, 0, '"high"', 4.5])
def test_a_score_outside_the_scale_is_flagged(judge, value):
    result = _rate(
        judge,
        _wrapped(
            f'{{"accuracy": {value}, "fluency": 7, "terminology": 9, '
            f'"justification": "x"}}'
        ),
    )

    assert result["scores"] == {}
    assert "accuracy" in result["error"]


def test_a_missing_criterion_is_flagged(judge):
    result = _rate(judge, _wrapped('{"accuracy": 8, "fluency": 7}'))

    assert result["scores"] == {}
    assert "terminology" in result["error"]


def test_api_errors_reach_the_caller(judge):
    """The command is the single place an API failure is handled."""
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


def test_candidates_reach_the_judge_anonymized(judge):
    """
    If a provider name leaks into the ranking prompt, every number the command
    prints afterwards is contaminated by brand preference.
    """
    with mock.patch.object(
        llm_providers,
        "completion",
        return_value=_response(_wrapped('{"ranks": {"A": 1, "B": 2}}')),
    ) as completion:
        result = judge.rank_translations(
            source_language="en",
            target_language="hi",
            source_content=SOURCE,
            candidates={"A": TRANSLATED, "B": TRANSLATED},
        )

    sent = completion.call_args.kwargs["messages"][1]["content"]
    assert "CANDIDATE A" in sent
    assert not any(
        name in sent for name in ("openai", "gemini", "anthropic", "mistral")
    )
    assert result["ranks"] == {"A": 1, "B": 2}


def test_a_rank_for_a_label_never_sent_is_flagged(judge):
    with mock.patch.object(
        llm_providers,
        "completion",
        return_value=_response(_wrapped('{"ranks": {"A": 1, "B": 2, "D": 3}}')),
    ):
        result = judge.rank_translations(
            source_language="en",
            target_language="hi",
            source_content=SOURCE,
            candidates={"A": TRANSLATED, "B": TRANSLATED},
        )

    assert result["ranks"] == {}
    assert "unknown label" in result["error"]


def test_anthropic_provider_prefixes_the_model():
    assert (
        AnthropicProvider("key", "claude-opus-5").model_name
        == "anthropic/claude-opus-5"
    )


# -------------------------------------------------------------- aggregation


def test_tied_scores_share_a_fractional_position():
    """Two candidates a judge cannot separate must not be separated by luck."""
    rows = {
        row.candidate: row for row in build_rows({"j1": {"a": 9.0, "b": 8.0, "c": 8.0}})
    }

    assert rows["a"].mean_rank == 1.0
    assert rows["b"].mean_rank == rows["c"].mean_rank == 2.5  # noqa: PLR2004


def test_mean_rank_is_averaged_over_the_judges_present():
    """A dropped judge must not leave a candidate ranked over a different set."""
    rows = {
        row.candidate: row
        for row in build_rows({"j1": {"a": 9.0, "b": 7.0}, "j2": {"a": 6.0, "b": 8.0}})
    }

    assert rows["a"].mean_rank == rows["b"].mean_rank == 1.5  # noqa: PLR2004
    assert rows["a"].judges == 2  # noqa: PLR2004
    assert rows["a"].spread == 1.0


def test_shortlist_keeps_candidates_tied_at_the_boundary():
    rows = [
        CandidateRow(candidate=name, mean_rank=rank, mean_score=0, spread=0)
        for name, rank in [("a", 1.0), ("b", 2.0), ("c", 3.0), ("d", 3.0), ("e", 5.0)]
    ]

    shortlisted = [row.candidate for row in select_shortlist(rows, size=3)]

    assert shortlisted == ["a", "b", "c", "d"]


def test_a_winner_needs_both_signals_to_agree():
    rows = build_rows({"j1": {"a": 9.0, "b": 7.0}, "j2": {"a": 9.0, "b": 7.0}})

    agreed, _ = pick_winner(rows, {"j1": {"a": 1, "b": 2}, "j2": {"a": 1, "b": 2}})
    disputed, reason = pick_winner(
        rows, {"j1": {"b": 1, "a": 2}, "j2": {"b": 1, "a": 2}}
    )

    assert agreed == "a"
    assert disputed is None
    assert "disagree" in reason


# ------------------------------------------------------------- the command


class FakeProvider:
    """Stands in for a real provider so the command's wiring can be exercised."""

    def __init__(self, spec, failing_candidate=None, *, failing_rank=False):
        self.spec = spec
        self.failing_candidate = failing_candidate
        self.failing_rank = failing_rank

    def translate_text(self, source_content, _target_language, **_kwargs):
        return f"<t by='{self.spec}'>{source_content}</t>"

    def validate_translation(self, *, translated_content, **_kwargs):
        return f"<v by='{self.spec}'>{translated_content}</v>"

    def rate_translation(self, *, translated_content, **_kwargs):
        if self.failing_candidate and self.failing_candidate in translated_content:
            return {"scores": {}, "justification": "", "error": "unparseable"}
        base = sum(translated_content.encode()) % 5
        return {
            "scores": {
                "accuracy": 5 + base,
                "fluency": 5 + (base + 1) % 5,
                "terminology": 5 + (base + 2) % 5,
            },
            "justification": f"scored by {self.spec}",
            "error": None,
        }

    def rank_translations(self, *, candidates, **_kwargs):
        if self.failing_rank:
            return {"ranks": {}, "error": "unparseable ranking"}
        return {
            "ranks": {
                label: position for position, label in enumerate(candidates, start=1)
            },
            "error": None,
        }


@pytest.fixture
def _providers(settings):
    settings.TRANSLATIONS_PROVIDERS = {
        "openai": {"api_key": FAKE_KEY, "default_model": "gpt-test"},
        "gemini": {"api_key": FAKE_KEY, "default_model": "gemini-test"},
    }
    settings.COURSE_TRANSLATIONS_SUPPORTED_LANGUAGES = {"en": "English", "hi": "Hindi"}


def _run(failing_judge=None, failing_candidate=None, failing_rank=None, **options):
    """Run the command with every provider replaced by a scripted fake."""

    def build(provider, model):
        spec = f"{provider}/{model}"
        fails_here = failing_candidate if spec == failing_judge else None
        return FakeProvider(spec, fails_here, failing_rank=spec == failing_rank)

    with mock.patch(
        "ol_openedx_course_translations.management.commands."
        "rate_translation_quality.get_translation_provider",
        side_effect=build,
    ):
        call_command(
            "rate_translation_quality", target_language="hi", yes=True, **options
        )


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers")
def test_a_run_records_every_candidate_and_score():
    _run(translators="openai,gemini", judges="openai,gemini")

    run = TranslationQualityRun.objects.get()
    candidates = TranslationQualityCandidate.objects.filter(run=run)
    scores = TranslationQualityScore.objects.filter(candidate__run=run)

    # 2 translators x (2 validators + the unvalidated arm)
    assert candidates.count() == 6  # noqa: PLR2004
    assert candidates.filter(validator="").count() == 2  # noqa: PLR2004
    assert scores.count() == 12  # noqa: PLR2004
    assert run.target_language == "hi"


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers")
def test_only_shortlisted_candidates_carry_a_comparative_rank():
    _run(translators="openai,gemini", judges="openai,gemini")

    ranked = TranslationQualityScore.objects.exclude(comparative_rank=None)
    shortlisted = {score.candidate_id for score in ranked}

    assert 2 <= len(shortlisted) <= 6  # noqa: PLR2004
    # Every judge ranked the same shortlist, and labelled each candidate.
    assert ranked.count() == len(shortlisted) * 2
    assert all(score.comparative_label for score in ranked)


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers")
def test_a_judge_that_fails_anywhere_is_dropped_from_the_whole_run():
    """
    Partial credit would rank candidates over different judge sets, so one bad
    reply costs that judge every row, not just the one it fumbled.
    """
    _run(
        failing_judge="gemini/gemini-test",
        failing_candidate="by='gemini/gemini-test'",
        translators="openai,gemini",
        judges="openai,gemini",
    )

    scores = TranslationQualityScore.objects.all()

    # The failing judge stumbled on 3 of the 6 candidates and keeps none of them.
    assert {score.judge for score in scores} == {"openai/gpt-test"}
    assert scores.count() == 6  # noqa: PLR2004


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers")
def test_a_repeated_roster_entry_is_collapsed():
    """'openai' and 'openai/gpt-test' are the same spec once resolved."""
    _run(translators="openai,openai/gpt-test", judges="openai")

    candidates = TranslationQualityCandidate.objects.all()

    assert candidates.count() == 2  # noqa: PLR2004
    assert {c.translator for c in candidates} == {"openai/gpt-test"}


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers")
def test_a_ranking_failure_costs_only_the_comparative_pass():
    """
    A judge that cannot rank keeps its scores.

    Mean rank comes from the scoring pass, so discarding those scores would
    shrink the judge set every candidate is ranked over — a worse outcome than
    losing one set of first-place votes.
    """
    _run(
        failing_rank="gemini/gemini-test",
        translators="openai,gemini",
        judges="openai,gemini",
    )

    scores = TranslationQualityScore.objects.all()
    ranked_judges = {score.judge for score in scores.exclude(comparative_rank=None)}

    assert {score.judge for score in scores} == {
        "openai/gpt-test",
        "gemini/gemini-test",
    }
    assert ranked_judges == {"openai/gpt-test"}
