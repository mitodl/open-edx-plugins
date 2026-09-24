"""
Tests for the translation quality benchmark.

Three layers: how a judge's reply is parsed, how scores become an ordering,
and whether the command joins those together and stores the result. The
command tests lean on a scripted provider whose output identifies which
translator produced it, so a mis-joined label or candidate fails loudly
instead of producing a plausible leaderboard.
"""

from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from litellm import BadRequestError
from ol_openedx_course_translations.admin import TranslationQualityRunAdmin
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
    Candidate,
    CandidateRow,
    average_overall,
    build_rows,
    pick_winner,
    rank_one_votes,
    select_shortlist,
)

FAKE_KEY = "not-a-real-key"  # pragma: allowlist secret
SOURCE = "<problem><p>Hello</p></problem>"
TRANSLATED = "<problem><p>नमस्ते</p></problem>"

# The command tests translate this instead of the real benchmark: small, and
# its two text units make a mis-joined candidate visible.
BENCHMARK = (
    '<problem display_name="Heat Transfer">'
    "<p>Conduction moves heat through solid material.</p>"
    "<p>Radiation needs no medium at all.</p>"
    "</problem>"
)
WINNER = "openai/gpt-test"


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

    assert result == {
        "scores": {"accuracy": 8, "fluency": 7, "terminology": 9},
        "justification": "ok",
    }


def test_scores_survive_a_fenced_and_chatty_reply(judge):
    """Models add prose and code fences whatever the prompt says."""
    reply = (
        "Sure! Here is my assessment:\n"
        "```json\n"
        '{"accuracy": 6, "fluency": 5, "terminology": 7, "justification": "fine"}\n'
        "```\n"
        "Let me know if you need more detail."
    )

    assert _rate(judge, reply)["scores"]["accuracy"] == 6  # noqa: PLR2004


def test_an_unparseable_reply_is_rejected(judge):
    """One failure channel: an untrustworthy reply raises, like an API error."""
    with pytest.raises(ValueError, match="no JSON object"):
        _rate(judge, "I would rather not score this one.")


@pytest.mark.parametrize("value", [11, 0, '"high"', 4.5])
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


def test_an_overall_is_the_mean_of_the_criteria():
    """Pinned against max/min/median, which all differ on this input."""
    assert average_overall({"accuracy": 9, "fluency": 3, "terminology": 6}) == 6.0  # noqa: PLR2004


def test_tied_scores_share_a_fractional_position():
    """Two candidates a judge cannot separate must not be separated by luck."""
    a, b, c = Candidate("a"), Candidate("b"), Candidate("c")
    rows = {row.candidate: row for row in build_rows({"j1": {a: 9.0, b: 8.0, c: 8.0}})}

    assert rows[a].mean_rank == 1.0
    assert rows[b].mean_rank == rows[c].mean_rank == 2.5  # noqa: PLR2004


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


@pytest.mark.parametrize(
    ("votes", "attempted", "expected"),
    [
        (2, 4, None),  # 2 of 4 is a plurality, not a majority
        (3, 4, "a"),
        (2, 3, "a"),
        (2, 2, "a"),
        (1, 5, None),  # one surviving judge is not a majority of five asked
    ],
)
def test_the_majority_boundary(votes, attempted, expected):
    a, b = Candidate("a"), Candidate("b")
    rows = build_rows({"j1": {a: 9.0, b: 7.0}, "j2": {a: 9.0, b: 7.0}})
    ranks = {f"j{index}": {a: 1, b: 2} for index in range(votes)}
    ranks.update(
        {f"loser{index}": {a: 2, b: 1} for index in range(attempted - votes - 1)}
    )

    winner, _ = pick_winner(rows, ranks, judges_attempted=attempted)

    assert (winner.translator if winner else None) == expected


def test_a_winner_needs_both_signals_to_agree():
    a, b = Candidate("a"), Candidate("b")
    rows = build_rows({"j1": {a: 9.0, b: 7.0}, "j2": {a: 9.0, b: 7.0}})

    agreed, _ = pick_winner(
        rows, {"j1": {a: 1, b: 2}, "j2": {a: 1, b: 2}}, judges_attempted=2
    )
    disputed, reason = pick_winner(
        rows, {"j1": {b: 1, a: 2}, "j2": {b: 1, a: 2}}, judges_attempted=2
    )

    assert agreed == a
    assert disputed is None
    assert "disagree" in reason


def test_a_tied_lead_is_not_a_winner():
    a, b = Candidate("a"), Candidate("b")
    rows = build_rows({"j1": {a: 9.0, b: 9.0}})

    winner, reason = pick_winner(rows, {"j1": {a: 1, b: 2}}, judges_attempted=1)

    assert winner is None
    assert "tied" in reason


# ------------------------------------------------------------- the command


class FakeProvider:
    """
    A scripted provider whose output says which translator produced it.

    Structure is preserved through translation and validation, because the
    command rejects an arm whose element count changes.
    """

    def __init__(self, spec, *, mode=None):
        self.spec = spec
        self.mode = mode

    def translate_text(self, source_content, _target_language, **_kwargs):
        if self.mode == "translate_raises":
            msg = "upstream refused"
            raise RuntimeError(msg)
        if self.mode == "translate_echoes":
            return source_content
        return (
            source_content.replace("Conduction moves", f"CONDUCCION[{self.spec}]")
            .replace("Radiation needs", f"RADIACION[{self.spec}]")
            .replace("Heat Transfer", f"CALOR[{self.spec}]")
        )

    def validate_translation(self, *, translated_content, **_kwargs):
        if self.mode == "validator_prose":
            return "Looks good to me!"
        if self.mode == "validator_restructures":
            return translated_content.replace("</problem>", "<p>extra</p></problem>")
        return translated_content.replace("CONDUCCION", "CONDUCCION!")

    def rate_translation(self, *, translated_content, **_kwargs):
        if self.mode == "score_rejects":
            msg = "unparseable"
            raise ValueError(msg)
        base = sum(translated_content.encode()) % 5
        return {
            "scores": {
                "accuracy": 5 + base,
                "fluency": 5 + (base + 1) % 5,
                "terminology": 5 + (base + 2) % 5,
            },
            "justification": f"scored by {self.spec}",
        }

    def rank_translations(self, *, candidates, **_kwargs):
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
def _benchmark(tmp_path):
    path = tmp_path / "benchmark_test.xml"
    path.write_text(BENCHMARK, encoding="utf-8")
    with mock.patch(
        "ol_openedx_course_translations.management.commands."
        "rate_translation_quality.BENCHMARK_PATH",
        path,
    ):
        yield path


def _run(modes=None, *, confirm=True, **options):
    """Run the command with every provider replaced by a scripted fake."""
    modes = modes or {}
    out = StringIO()

    def build(provider, model):
        spec = f"{provider}/{model}"
        return FakeProvider(spec, mode=modes.get(spec))

    with mock.patch(
        "ol_openedx_course_translations.management.commands."
        "rate_translation_quality.get_translation_provider",
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
@pytest.mark.usefixtures("_providers", "_benchmark")
def test_a_run_records_every_candidate_and_score():
    _run(translators="openai,gemini", judges="openai,gemini")

    run = TranslationQualityRun.objects.get()
    candidates = TranslationQualityCandidate.objects.filter(run=run)

    # 2 translators x (2 validators + the unvalidated arm)
    assert candidates.count() == 6  # noqa: PLR2004
    assert candidates.filter(validator="").count() == 2  # noqa: PLR2004
    assert TranslationQualityScore.objects.count() == 12  # noqa: PLR2004
    assert run.target_language == "hi"
    assert run.judges_arg == "openai/gpt-test,gemini/gemini-test"


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "_benchmark")
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
@pytest.mark.usefixtures("_providers", "_benchmark")
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
@pytest.mark.usefixtures("_providers", "_benchmark")
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
    assert broken.count() == 3  # every arm of that translator  # noqa: PLR2004
    assert {candidate.translator for candidate in broken} == {"gemini/gemini-test"}
    assert not TranslationQualityScore.objects.filter(
        candidate__translator="gemini/gemini-test"
    ).exists()
    assert "source unchanged" in output


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "_benchmark")
def test_a_translator_failure_still_records_all_of_its_arms():
    _run(
        modes={"gemini/gemini-test": "translate_raises"},
        translators="openai,gemini",
        judges="openai",
    )

    arms = TranslationQualityCandidate.objects.filter(translator="gemini/gemini-test")

    assert arms.count() == 3  # noqa: PLR2004
    assert all("translation failed" in arm.error for arm in arms)


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "_benchmark")
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
@pytest.mark.usefixtures("_providers", "_benchmark")
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
@pytest.mark.usefixtures("_providers", "_benchmark")
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
    # The label belongs to a completed ranking only.
    assert (
        not scores.filter(judge="gemini/gemini-test")
        .exclude(comparative_label="")
        .exists()
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "_benchmark")
def test_a_repeated_roster_entry_is_collapsed():
    """'openai' and 'openai/gpt-test' are the same spec once resolved."""
    _run(translators="openai,openai/gpt-test", judges="openai")

    candidates = TranslationQualityCandidate.objects.all()

    assert candidates.count() == 2  # noqa: PLR2004
    assert {candidate.translator for candidate in candidates} == {WINNER}


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "_benchmark")
def test_the_default_roster_skips_providers_without_a_key():
    output, _ = _run()

    run = TranslationQualityRun.objects.get()

    assert run.translators_arg == "openai/gpt-test,gemini/gemini-test"
    assert "skipped translator mistral: no api_key" in output
    # "default_provider" is a string in that setting, not a provider entry.
    assert "default_provider" not in run.translators_arg


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "_benchmark")
def test_a_provider_named_by_hand_but_unconfigured_is_fatal():
    """Silently skipping it would answer a different question than the one asked."""
    with pytest.raises(CommandError, match="Unknown translator provider 'opneai'"):
        _run(translators="opneai", judges="openai")


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "_benchmark")
def test_declining_the_prompt_spends_nothing():
    with (
        mock.patch("builtins.input", return_value="n"),
        pytest.raises(CommandError, match="Aborted"),
    ):
        _run(confirm=False, translators="openai", judges="openai")

    assert not TranslationQualityRun.objects.exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("_providers", "_benchmark")
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
@pytest.mark.usefixtures("_providers", "_benchmark")
def test_the_admin_report_ranks_the_same_way_the_command_does():
    """
    The admin re-derives the standings from stored rows.

    Swapping its two aggregation levels renders a plausible table built from
    judges-as-candidates, which only an assertion on the leader catches.
    """
    _run(translators="openai,gemini", judges="openai,gemini")
    run = TranslationQualityRun.objects.get()

    html = TranslationQualityRunAdmin(TranslationQualityRun, mock.Mock()).report(run)
    rows = [row for row in html.split("<tr>") if "<td>" in row]
    leader = rows[0]

    assert len(rows) == TranslationQualityCandidate.objects.count()
    assert "→" in leader
    # The leader must be a candidate, not a judge spec rendered as one.
    assert any(
        f"<td>{candidate.translator} → {candidate.validator or 'none'}</td>" in leader
        for candidate in TranslationQualityCandidate.objects.all()
    )
