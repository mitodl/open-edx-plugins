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
from itertools import groupby
from operator import itemgetter
from statistics import fmean
from typing import NamedTuple

SHORTLIST_SIZE = 5
SHORTLIST_CAP = 8


class Candidate(NamedTuple):
    """
    One (translator, validator) pairing under test.

    ``validator`` is empty only on rows from runs made when the unvalidated
    translation was itself a candidate, and on the source row while it exists
    mid-run. Both still have to render.
    """

    translator: str
    validator: str = ""

    def __str__(self) -> str:
        """Render the pairing the way the report and the admin both show it."""
        return f"{self.translator} → {self.validator or 'none'}"


@dataclass(frozen=True)
class Rating:
    """One judge's scores for one candidate."""

    scores: dict[str, int]
    justification: str


@dataclass(frozen=True)
class CandidateRow:
    """One candidate's standing across the judges that scored it."""

    candidate: Candidate
    # None in comparative-only mode: nothing was scored on the 1-10 scale, and
    # a zero there would read as a score rather than as an absence.
    mean_score: float | None
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
    for _, group in groupby(ordered, key=itemgetter(1)):
        tied = [candidate for candidate, _overall in group]
        positions.update(dict.fromkeys(tied, index + (len(tied) + 1) / 2))
        index += len(tied)
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
        rows,
        key=lambda row: (row.mean_rank, -(row.mean_score or 0.0), str(row.candidate)),
    )


def build_comparative_rows(
    ranks_by_judge: dict[str, dict[Candidate, int]],
) -> list[CandidateRow]:
    """
    Rank candidates by mean comparative rank, best first.

    Used when the scoring pass is skipped. A judge's ranks already are
    positions on a shared 1..N scale from one call, so unlike ``build_rows``
    there is nothing to convert — they are averaged as they stand.
    """
    candidates = {candidate for ranks in ranks_by_judge.values() for candidate in ranks}
    rows = [
        CandidateRow(
            candidate=candidate,
            mean_score=None,
            positions={
                judge: float(ranks[candidate])
                for judge, ranks in ranks_by_judge.items()
                if candidate in ranks
            },
        )
        for candidate in candidates
    ]
    return sorted(rows, key=lambda row: (row.mean_rank, str(row.candidate)))


def pick_comparative_winner(
    rows: list[CandidateRow],
) -> tuple[Candidate | None, str]:
    """
    Name the best candidate from the comparative pass alone.

    One pass means one signal, so there is no second opinion to agree with:
    the lowest mean comparative rank wins outright. A tie at the top is the
    only refusal, because nothing in this mode can break it.
    """
    if not rows:
        return None, "no candidates were ranked"
    leaders = [row for row in rows if row.mean_rank == rows[0].mean_rank]
    if len(leaders) > 1:
        tied = ", ".join(str(row.candidate) for row in leaders)
        return None, f"mean comparative rank is tied between {tied}"
    return rows[0].candidate, "lowest mean comparative rank"


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
    is a judge count. The same guard covers a judge with no rank 1 at all — the
    parser bounds each rank but never requires a 1 to be present.
    """
    votes: dict[Candidate, int] = {}
    for ranks in comparative_ranks.values():
        firsts = [candidate for candidate, position in ranks.items() if position == 1]
        if len(firsts) != 1:
            continue
        votes[firsts[0]] = votes.get(firsts[0], 0) + 1
    return votes
