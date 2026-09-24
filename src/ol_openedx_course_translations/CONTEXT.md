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
changing no markup. A candidate may have no validator at all.
_Avoid_: editor, reviewer, proofreader

**Judge**:
A provider/model that scores or ranks translations. A judge never translates or edits anything.
_Avoid_: rater, evaluator, grader

### Benchmarking

**Benchmark**:
The committed course-unit OLX that every benchmark run translates. Fixed on purpose, so scores
stay comparable across languages and over time.
_Avoid_: sample, test content

**Candidate**:
One (translator, validator-or-none) pairing under test, together with the translation it produced.
The thing a judge scores.
_Avoid_: combination, configuration, variant

**Run**:
A single invocation of the benchmark command for one target language.
_Avoid_: job, experiment, batch

**Mean rank**:
A candidate's average position across the judges that scored it, where each judge's positions come
from sorting its own scores. Lower is better. The single ordering statistic for a run.
_Avoid_: score, rating, average

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
