---
status: accepted
date: 2026-09-25
---

# Score candidates absolutely, then let a comparative pass of the leaders decide the winner

Choosing the best translator/validator pairing for a language was a manual ritual — translate a
unit with each model, paste the results into chat UIs for an opinion, average the answers by eye.
The `rate_translation_quality` command replaces it.

A **candidate** is a (translator, validator) pairing; a run covers every combination of the roster
with itself, `translators × translators` of them. Every candidate is scored **absolutely** by every
judge (three criteria, 1–10, one candidate per call). Candidates are ordered by **mean rank** —
each judge's own scores sorted into positions, then averaged across judges — and the leaders, the
top five plus anything tied with fifth capped at eight, go into a **comparative** pass where each
judge ranks them side by side, anonymised and shuffled per judge.

**The comparative pass decides the winner**: the candidate with the lowest mean comparative rank,
refused only when the top is tied. Mean rank orders the standings and selects the shortlist; it
does not decide anything.

## Considered options

**Requiring both passes to agree before naming a winner.** Rejected, having been tried. The rule
declared a winner only when the best mean rank also took a majority of first-place votes. The first
live run (12 candidates, 2 judges, Hindi) produced exactly the case it was built for and handled it
badly: the mean-rank leader sat at 1.75 while both judges independently ranked it 4th and 5th of
six head to head, and the candidate both judges put in their top two sat second on mean rank. The
rule returned "no clear winner", which reads as *the judges disagreed* when in fact the two
measurements disagreed and the comparative one is the better evidence.

The passes are not equally informative. Absolute scores compressed the top six into 0.67 of a point
on a 1–10 scale, so one criterion moving by one flipped two rank positions. The comparative pass
asks the question the run exists to answer — which of these is better — with the texts in front of
the judge at once. Requiring the weaker measurement to ratify the stronger one made the tool refuse
to answer precisely when the answer was interesting. A majority of first-place votes also scales
badly at the small end: with two judges a majority requires unanimity, so the cheapest panel is the
one where the rule almost never fires.

**One comparative call per judge over all candidates, as the default.** Rejected. With 4 translators
× 4 validators there are 16 near-identical documents; attention over a long input is U-shaped, so
the middle of the list is read least reliably, and a strict total ordering demands ~120 pairwise
distinctions a judge cannot support. A well-formed permutation with no signal in its middle is
worse than an honest absolute score, because it looks like data. It is available as
`--comparative-only` for cheap runs, with that cost understood — see Consequences.

**Absolute scoring alone.** Rejected as insufficient. Absolute rubric scores cluster hard, and with
single-pass judging there is no variance estimate to separate a real 0.2 gap from noise. Comparison
is what gives a judge a reference point, so it is applied where decisions are actually made — among
the leaders.

**Mean of raw scores as the ordering statistic.** Rejected. Judges use the scale differently; one
spreading its scores across 6–9.5 outvotes one squeezed into 7.8–8.3 purely because it moves more.
Mean rank normalises every judge to one equal vote.

**Mean z-score per judge.** Rejected, though it fixes the same problem while keeping magnitude. It
standardises using a mean and standard deviation estimated in-sample from coarse values, is not
robust to outliers, and is not interpretable to a human reading the report.

**Keeping the unvalidated translation as a candidate.** Rejected. It answered a different question
from the rest of the run: with it, a run measures *whether validating helps*; without it, *which
validator is best*. The first run answered the first question emphatically — an unvalidated arm
placed last at mean rank 12.00 against 2.75 for the same translator validated — and that is not
worth re-paying for on every run. The arm is still translated, because every validator arm is built
from it, and is deleted once they are.

**Ranking by comparative rank in the standings too.** Rejected for the default mode. Mean rank is
what selects the shortlist, so the table must show the ordering the shortlist was drawn from. In
`--comparative-only` there is no scoring pass, so the comparative ranks *are* the table.

**Committing the benchmark content to the repository.** Rejected. The content worth benchmarking
is real course material, whose licence is rarely the package's to grant — a permissively licensed
wheel would be redistributing it. The benchmark is a course block instead, named by its usage key,
so nothing third-party is committed or published and the content is already where translation
happens.

**Storing the content in a plugin-owned table.** Tried, then rejected. It solved the licence
problem but duplicated content the CMS already holds, needed an authoring UI, a freeze rule and a
protected foreign key to keep old runs readable, and still left the plugin's copy able to drift
from the course. A usage key is the smaller answer: one field on the run, no second source of
truth. The cost is that the block is live — two runs naming the same block are comparable only if
nobody republished it between them, which the frozen table did guarantee. Within one run each
worker process caches its read, so a republish mid-run reaches only the workers that have not yet
read the block, or that have since evicted it — it no longer splits the arms one worker produced.
The cache is keyed on the run, which already records the block, so it narrows that window without
widening the cross-run one: a second run always reads afresh.

## Consequences

Scores are only comparable to other scores produced the same way, and only within one benchmark
block that nobody has republished. Changing the criteria, the 1–10 scale, the ordering statistic or
the candidate population silently invalidates comparisons with earlier runs — so those changes
belong in a new ADR and, ideally, a new benchmark identity.

**No run can measure the value of validation itself**, only which validator is best. Recovering
that means reinstating the unvalidated arm, not reading around the data.

Deleting the unvalidated row discards the only record of the provider's own failure message, so it
is copied onto the dependent arms first — otherwise a failed translation leaves every one of its
arms saying "translation failed" with no cause.

Only what a judge returned is persisted — the per-criterion scores, the comparative rank, the label
it saw and its justification. Mean rank, mean comparative rank and every other aggregate is derived
at report time, so a future change to the aggregation needs no migration and leaves historical runs
recomputable.

Each translator translates the benchmark once and that translation is reused across all of its
validator arms, so those arms differ only by validator. The cost is that each validator verdict
rides on a single translation sample, which single-pass judging does not average out.

A judge whose reply cannot be parsed in the **scoring** pass is dropped from that pass entirely
rather than from one candidate, so every candidate is ranked over an identical judge set. A judge
that fails only the **comparative** pass keeps its scores and drops out of the verdict alone:
discarding its scores would shrink the judge set for every candidate to punish one malformed reply.
Either way the reason is stored on the run, including on the paths that then refuse it, so a run
whose standings are thin says why rather than leaving it to the console scrollback.

**An unreadable benchmark block is the run's failure until the run has something to report, and one
judge's after that.** Every task reads the block, so treating a failed read as the task's own would
blame each provider that happened to hit it, durably, on the arms and on the run. While nothing has
been paid for — the translate stage — the run therefore stops and names the block. After that it
does not: the read is cached per worker process per run, so a failure is one cold worker's, and
aborting would discard work already bought. From the validate stage on it is recorded against the
arm or the judge that hit it, with the block named in the reason. The cost is that a block deleted
mid-run yields a run scored over fewer judges than it asked for, which the stored reasons disclose
but the aggregate does not.

`--comparative-only` skips the scoring pass and ranks every candidate in one call per judge,
reducing a run from `candidates × judges + judges` judging calls to `judges`. It is the option
rejected above, offered deliberately as a cheap approximation rather than the recommended mode, and
it gives up the absolute scores, the mean-score column and the shortlist. It refuses to run when
the candidates outnumber the 26 anonymous labels one call can carry, because the label mapping
would otherwise drop the excess silently.

Benchmark content is translated as HTML, not XML: an html block's body is a fragment with no
single root, and production picks `tag_handling` from the file suffix, so XML mode would have
measured a shape production never translates. Only `html` blocks are accepted for the same
reason — a `problem` block also has a `data` body, but it exports as `.xml` and production
translates it as XML, so benchmarking it as HTML would measure the mismatch this decision
exists to remove.

The HTML parser recovers from malformed markup, so there is no well-formedness gate. It returns
no root at all for a document with no element node — a lone comment or DOCTYPE — which counts as
no translatable text rather than raising. A block is therefore rejected for being the wrong type,
having no markup body, or having no translatable text.

`TranslationQualityScore.accuracy`, `.fluency` and `.terminology` are nullable, so a
comparative-only run writes one row per (candidate, judge) carrying only the rank, and the admin
reads one shape whichever mode produced the run. Any average taken over mixed runs must exclude
nulls rather than treat them as zero.
