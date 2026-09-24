---
status: accepted
date: 2026-09-23
---

# Benchmark translation quality with absolute scoring, then comparative ranking of the leaders

Choosing the best translator/validator pairing for a language was a manual ritual — translate a
unit with each model, paste the results into chat UIs for an opinion, average the answers by eye.
The `rate_translation_quality` command replaces it: every candidate is scored **absolutely** by
every judge (three criteria, 1–10, one candidate per call), candidates are ordered by **mean rank**
(each judge's own scores sorted into positions, then averaged across judges), and only the top five
go into a second **comparative** pass where each judge ranks them side by side. A winner is
declared only when the best mean rank and a majority of comparative first-place votes agree.

## Considered options

**One comparative call per judge over all candidates.** Rejected. With 4 translators × 4 validators
plus the unvalidated arms there are 20 near-identical documents; attention over a long input is
U-shaped, so the middle of the list is read least reliably, and a strict 1..20 ordering demands
~190 pairwise distinctions a judge cannot support. A well-formed permutation with no signal in its
middle is worse than an honest absolute score, because it looks like data.

**Absolute scoring alone.** Rejected as insufficient. Absolute rubric scores cluster hard, and with
single-pass judging there is no variance estimate to separate a real 0.2 gap from noise. Comparison
is what gives a judge a reference point, so it is applied where decisions are actually made — among
the leaders.

**Mean of raw scores as the ordering statistic.** Rejected. Judges use the scale differently; one
spreading its scores across 6–9.5 outvotes one squeezed into 7.8–8.3 purely because it moves more.
Mean rank normalises every judge to one equal vote.

**Mean z-score per judge.** Rejected, though it fixes the same problem while keeping magnitude. It
standardises using a mean and standard deviation estimated in-sample from 20 coarse values, is not
robust to outliers, and is not interpretable to a human reading the report.

## Consequences

Scores are only comparable to other scores produced the same way. Changing the criteria, the 1–10
scale, the benchmark content, or the ordering statistic silently invalidates comparisons with
earlier runs — so those changes belong in a new ADR and, ideally, a new benchmark identity.

Only raw per-criterion scores and comparative ranks are persisted; mean rank and every other
aggregate is derived at report time. A future change to the aggregation therefore needs no
migration and leaves historical runs recomputable.

Each translator translates the benchmark once and that translation is reused across all of its
validator arms, so those arms differ only by validator. The cost is that each validator verdict
rides on a single translation sample, which single-pass judging does not average out.

A judge whose reply cannot be parsed is dropped from the entire run rather than from one candidate,
so every candidate is ranked over an identical judge set.
