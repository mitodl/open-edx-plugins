# Course Translations

Translates Open edX course content and subtitles into other languages using LLM providers, and
benchmarks those providers against each other so the best configuration for a language can be
chosen from evidence rather than guesswork.

## Language

### Providers and roles

**Provider**:
A credentialed LLM service configured in `TRANSLATIONS_PROVIDERS`, named by its litellm prefix
(`openai`, `gemini`, `mistral`, `anthropic`). A provider is not a role — the same provider can act
as a translator, a validator and a judge in one run, so name the role when describing behaviour.

**Translator**:
A provider/model that renders source content into the target language.
_Avoid_: translation provider, translation engine

**Validator**:
A provider/model that reviews an existing translation and corrects only linguistic errors,
changing no markup. Every candidate has one: the unvalidated translation is produced so validators
have something to read, then discarded.
_Avoid_: editor, reviewer, proofreader

**Judge**:
A provider/model that scores or ranks translations. A judge never translates or edits anything.
_Avoid_: rater, evaluator, grader

### Benchmarking

**Benchmark**:
The published body of the course block a run translates, named by its usage key. Live content, so
two runs naming the same block are comparable only if nobody republished it between them.
_Avoid_: sample, test content, fixture

**Candidate**:
One (translator, validator) pairing under test, together with the translation it produced. The
thing a judge scores. A run has `translators x translators` of them.
_Avoid_: combination, configuration, variant

**Run**:
A single invocation of the benchmark command for one target language.
_Avoid_: job, experiment, batch

**Mean rank**:
A candidate's average position across the judges that scored it, where each judge's positions come
from sorting its own scores. Lower is better. Orders the standings and selects the shortlist; it
does not decide the winner.
_Avoid_: score, rating, average

**Mean comparative rank**:
A candidate's average rank across the judges that ranked it in the side-by-side pass. Lower is
better. The statistic the winner is chosen by, in either mode.
_Avoid_: mean rank (that is the scoring pass's statistic)

**Scoring pass**:
The stage where each judge scores one candidate at a time, in isolation, on three criteria from
1 to 10. Skipped by `--comparative-only`.
_Avoid_: phase 1, absolute pass

**Comparative pass**:
The stage where each judge ranks several candidates seen side by side, anonymised and shuffled per
judge. Ranks only, never scores. Always decides the winner.
_Avoid_: phase 2, ranking round

### Translation pipeline

**Translation unit**:
One piece of translatable text extracted from a document — a text node, a tail, or an allowlisted
attribute value. On the translation path a provider is sent units, never markup; validation and
judging deliberately send whole documents instead.
_Avoid_: chunk, segment, string

**Glossary**:
Language-specific `source_term : translated_term` pairs injected into a prompt to pin terminology.
Content and subtitle translation can use different glossaries.
_Avoid_: dictionary, termbase
