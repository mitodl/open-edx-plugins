"""
Aggregation for translation quality benchmark runs.

Judges score each candidate on its own, so a judge's opinion of the field is
recovered by sorting its own scores into positions. Mean rank across judges is
the single ordering statistic: it gives every judge one equal vote regardless
of how wide or narrow a range that judge happens to use.

These functions take plain data rather than model instances so the command can
report before anything is written, and the admin can report from stored rows.
"""

from dataclasses import dataclass, field
from statistics import fmean
from typing import Any

SHORTLIST_SIZE = 5
SHORTLIST_CAP = 8


@dataclass
class CandidateRow:
    """One candidate's aggregate standing across all judges."""

    candidate: Any
    mean_rank: float
    mean_score: float
    spread: float
    positions: dict[str, float] = field(default_factory=dict)

    @property
    def judges(self) -> int:
        """How many judges contributed to this row."""
        return len(self.positions)


def average_overall(scores: dict[str, int]) -> float:
    """Collapse one judge's per-criterion scores into a single overall."""
    return fmean(scores.values())


def _positions(overalls: dict[Any, float]) -> dict[Any, float]:
    """
    Turn one judge's scores into 1-based positions, best first.

    Tied candidates share the mean of the positions they span. Without that,
    the order they happened to arrive in would become real signal — and ties
    are common, since an overall is the mean of three small integers.
    """
    ordered = sorted(overalls.items(), key=lambda item: -item[1])
    positions: dict[Any, float] = {}
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


def build_rows(overalls_by_judge: dict[str, dict[Any, float]]) -> list[CandidateRow]:
    """
    Rank candidates by mean rank, best first.

    ``overalls_by_judge`` maps a judge to that judge's overall per candidate.
    Ties on mean rank keep a stable order, so the caller can widen a shortlist
    by value rather than by position.
    """
    positions_by_judge = {
        judge: _positions(overalls) for judge, overalls in overalls_by_judge.items()
    }

    rows = []
    for candidate in {c for overalls in overalls_by_judge.values() for c in overalls}:
        positions = {
            judge: positions[candidate]
            for judge, positions in positions_by_judge.items()
            if candidate in positions
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
                mean_rank=fmean(positions.values()),
                mean_score=fmean(scores),
                spread=max(positions.values()) - min(positions.values()),
                positions=positions,
            )
        )

    return sorted(rows, key=lambda row: (row.mean_rank, -row.mean_score))


def select_shortlist(
    rows: list[CandidateRow],
    size: int = SHORTLIST_SIZE,
    cap: int = SHORTLIST_CAP,
) -> list[CandidateRow]:
    """
    Take the leading candidates for the comparative pass.

    Candidates tied with the last one in are kept too: separating them would
    mean leaning on the statistic that has just failed to separate them. The
    cap stops a run where everything ties from putting the whole field into a
    single comparative call.
    """
    if len(rows) <= size:
        return list(rows)

    cutoff = rows[size - 1].mean_rank
    shortlist = [row for row in rows if row.mean_rank <= cutoff]
    return shortlist[:cap]


def rank_one_votes(comparative_ranks: dict[str, dict[Any, int]]) -> dict[Any, int]:
    """Count first-place votes per candidate from the comparative pass."""
    votes: dict[Any, int] = {}
    for ranks in comparative_ranks.values():
        for candidate, position in ranks.items():
            if position == 1:
                votes[candidate] = votes.get(candidate, 0) + 1
    return votes


def pick_winner(
    rows: list[CandidateRow],
    comparative_ranks: dict[str, dict[Any, int]],
) -> tuple[Any | None, str]:
    """
    Name a winner only when both signals agree.

    The two signals are independent: mean rank comes from judges scoring
    candidates in isolation, first-place votes from judges comparing them side
    by side. With a single pass and no variance estimate, their agreement is
    the only confidence signal available, so a disagreement is reported rather
    than resolved.
    """
    if not rows:
        return None, "no candidates were scored"

    leaders = [row for row in rows if row.mean_rank == rows[0].mean_rank]
    if len(leaders) > 1:
        tied = ", ".join(str(row.candidate) for row in leaders)
        return None, f"mean rank is tied between {tied}"

    votes = rank_one_votes(comparative_ranks)
    if not votes:
        return None, "no judge returned a usable ranking"

    best_votes = max(votes.values())
    voted = [candidate for candidate, count in votes.items() if count == best_votes]
    if len(voted) > 1 or best_votes * 2 <= len(comparative_ranks):
        return None, "no candidate took first place from a majority of judges"

    if voted[0] != rows[0].candidate:
        disagreement = (
            f"best mean rank ({rows[0].candidate}) and the majority first-place "
            f"vote ({voted[0]}) disagree"
        )
        return None, disagreement
    return rows[0].candidate, "best mean rank and the majority first-place vote agree"
