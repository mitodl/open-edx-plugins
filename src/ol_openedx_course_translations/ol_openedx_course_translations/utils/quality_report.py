"""
Aggregation for translation quality benchmark runs.

Judges score each candidate on its own, so a judge's opinion of the field is
recovered by sorting its own scores into positions. Mean rank across judges is
the single ordering statistic: it gives every judge one equal vote regardless
of how wide or narrow a range that judge happens to use.

These functions take plain data rather than model instances, so the command can
aggregate from in-memory results and the admin from stored rows.
"""

from dataclasses import dataclass
from statistics import fmean
from typing import NamedTuple

SHORTLIST_SIZE = 5
SHORTLIST_CAP = 8


class Candidate(NamedTuple):
    """One (translator, validator-or-none) pairing under test."""

    translator: str
    validator: str = ""

    def __str__(self) -> str:
        """Render the pairing the way the report and the admin both show it."""
        return f"{self.translator} → {self.validator or 'none'}"


@dataclass(frozen=True)
class CandidateRow:
    """One candidate's standing across the judges that scored it."""

    candidate: Candidate
    mean_score: float
    positions: dict[str, float]

    @property
    def mean_rank(self) -> float:
        return fmean(self.positions.values())

    @property
    def spread(self) -> float:
        return max(self.positions.values()) - min(self.positions.values())

    @property
    def judges(self) -> int:
        return len(self.positions)


def average_overall(scores: dict[str, int]) -> float:
    """Collapse one judge's per-criterion scores into a single overall."""
    return fmean(scores.values())


def _positions(overalls: dict[Candidate, float]) -> dict[Candidate, float]:
    """
    Turn one judge's scores into 1-based positions, best first.

    Tied candidates share the mean of the positions they span. Without that,
    the order they happened to arrive in would become real signal — and ties
    are common, since an overall is the mean of a handful of small integers.
    """
    ordered = sorted(overalls.items(), key=lambda item: -item[1])
    positions: dict[Candidate, float] = {}
    index = 0
    while index < len(ordered):
        last = index
        while last + 1 < len(ordered) and ordered[last + 1][1] == ordered[index][1]:
            last += 1
        shared = (index + last) / 2 + 1
        for candidate, _ in ordered[index : last + 1]:
            positions[candidate] = shared
        index = last + 1
    return positions


def build_rows(
    overalls_by_judge: dict[str, dict[Candidate, float]],
) -> list[CandidateRow]:
    """
    Rank candidates by mean rank, best first.

    ``overalls_by_judge`` maps a judge to that judge's overall per candidate. A
    candidate is scored by every judge in a command run, but the admin
    aggregates whatever rows happen to be stored, so partial coverage is
    tolerated and reflected in each row's judge count.
    """
    positions_by_judge = {
        judge: _positions(overalls) for judge, overalls in overalls_by_judge.items()
    }
    candidates = {
        candidate for overalls in overalls_by_judge.values() for candidate in overalls
    }

    rows = []
    for candidate in candidates:
        positions = {
            judge: judge_positions[candidate]
            for judge, judge_positions in positions_by_judge.items()
            if candidate in judge_positions
        }
        if not positions:
            continue
        scores = [
            overalls[candidate]
            for overalls in overalls_by_judge.values()
            if candidate in overalls
        ]
        rows.append(
            CandidateRow(
                candidate=candidate,
                mean_score=fmean(scores),
                positions=positions,
            )
        )

    # The candidate is the final sort key so that two rows tied on both
    # statistics still order the same way every run: without it the order would
    # follow set iteration, and the shortlist cap could fall differently on
    # identical data.
    return sorted(
        rows, key=lambda row: (row.mean_rank, -row.mean_score, str(row.candidate))
    )


def select_shortlist(
    rows: list[CandidateRow],
    size: int = SHORTLIST_SIZE,
    cap: int = SHORTLIST_CAP,
) -> list[CandidateRow]:
    """
    Take the leading candidates for the comparative pass.

    Candidates tied with the last one in are kept too: separating them would
    mean leaning on the statistic that has just failed to separate them. The
    exception is a tie wider than ``cap``, which is truncated by position —
    accepted as the lesser evil, since putting the whole field into one
    comparative call is what the second pass exists to avoid.
    """
    if len(rows) <= size:
        return list(rows)

    cutoff = rows[size - 1].mean_rank
    shortlist = [row for row in rows if row.mean_rank <= cutoff]
    return shortlist[:cap]


def rank_one_votes(comparative_ranks: dict[str, dict[Candidate, int]]) -> dict:
    """
    Count first-place votes, at most one per judge.

    A judge that put two candidates at rank 1 named no single best, so it casts
    no vote: counting both would let one judge outvote the denominator, which
    is a judge count.
    """
    votes: dict[Candidate, int] = {}
    for ranks in comparative_ranks.values():
        firsts = [candidate for candidate, position in ranks.items() if position == 1]
        if len(firsts) != 1:
            continue
        votes[firsts[0]] = votes.get(firsts[0], 0) + 1
    return votes


def pick_winner(
    rows: list[CandidateRow],
    comparative_ranks: dict[str, dict[Candidate, int]],
    judges_attempted: int | None = None,
) -> tuple[Candidate | None, str]:
    """
    Name a winner only when both signals agree.

    The two signals are independent: mean rank comes from judges scoring
    candidates in isolation, first-place votes from judges comparing them side
    by side. With a single pass and no variance estimate, their agreement is
    the only confidence signal available, so a disagreement is reported rather
    than resolved.

    ``judges_attempted`` is the number of judges *asked* to rank, which is the
    honest majority denominator: judges whose ranking was rejected are absent
    from ``comparative_ranks``, so counting only the survivors would let one
    judge out of five carry a "majority".
    """
    if not rows:
        return None, "no candidates were scored"

    leaders = [row for row in rows if row.mean_rank == rows[0].mean_rank]
    if len(leaders) > 1:
        tied = ", ".join(str(row.candidate) for row in leaders)
        return None, f"mean rank is tied between {tied}"

    denominator = (
        len(comparative_ranks) if judges_attempted is None else judges_attempted
    )
    votes = rank_one_votes(comparative_ranks)
    if not votes:
        return None, "no judge named a single best candidate"

    best_votes = max(votes.values())
    voted = [candidate for candidate, count in votes.items() if count == best_votes]
    if len(voted) > 1 or best_votes * 2 <= denominator:
        shortfall = (
            f"no candidate took first place from a majority of the "
            f"{denominator} judge(s) asked to rank"
        )
        return None, shortfall

    if voted[0] != rows[0].candidate:
        disagreement = (
            f"best mean rank ({rows[0].candidate}) and the majority first-place "
            f"vote ({voted[0]}) disagree"
        )
        return None, disagreement
    return rows[0].candidate, "best mean rank and the majority first-place vote agree"
