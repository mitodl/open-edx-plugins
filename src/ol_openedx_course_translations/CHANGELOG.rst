Change Log
----------

..
   All enhancements and patches to ol_openedx_course_translations will be documented
   in this file.  It adheres to the structure of https://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (https://semver.org/).
.. There should always be an "Unreleased" section for changes pending release.

Unreleased
----------

Changed
~~~~~~~
- ``rate_translation_quality`` dispatches its work as Celery tasks on the CMS
  workers instead of an in-process thread pool. A 10-translator, 4-judge run is
  ~550 calls, which one process serialises into hours; the three CMS workers
  offer 18 slots. Tasks go to ``edx.cms.core.low``, retry only on ``Timeout``
  and ``RateLimitError``, and each stage is awaited before the next begins.
- ``TranslationQualityCandidate`` keeps the content each arm was scored on, so
  tasks address rows by id rather than passing documents through the broker,
  and a stored verdict can be checked against the text behind it.

Fixed
~~~~~
- Judging calls are bounded and no longer retried by the provider client.
  Scoring and ranking inherited the 300s provider default and the client's two
  retries, so one hang could hold a worker slot for 15 minutes. Validation from
  the benchmark now allows 240s with retries off — the same worst case as
  before, but a slow-but-working model gets to finish instead of failing three
  times.
- Gemini now asks for ``temperature=1.0`` rather than 0.0. Gemini 3 accepts a
  lower value without error and then behaves badly on it — litellm warns it
  "can cause infinite loops, degraded reasoning performance, and failure on
  complex tasks", which showed up as whole-document validation calls hanging
  until they timed out while the smaller chunked translation calls succeeded.
- ``_call_llm`` no longer probes the same temperature twice when a provider
  already asks for the fallback value.

[0.11.0] - 2026-09-24
---------------------

Added
~~~~~
- ``rate_translation_quality`` management command. Translates a fixed benchmark
  unit with every configured translator, edits each translation with every
  validator (keeping an unvalidated arm), has every judge score the results,
  and reports which translator/validator pairing wins. Candidates are ordered
  by mean rank, and a winner is named only when the best mean rank and a
  majority of first-place votes agree — at most one vote per judge, measured
  against the judges asked to rank. Results are stored in
  ``TranslationQualityRun``, ``TranslationQualityCandidate`` and
  ``TranslationQualityScore``, and readable in the Django admin. A judge
  dropped from the scoring pass is recorded on the run with the reason, so a
  stored run says why it rests on fewer judges rather than leaving it to be
  inferred from missing rows.
- The report counts translation units a provider handed back identical to the
  source, so a partially translated document can be recognised as such rather
  than read as the model's judgement. Diagnostic only: it is not part of the
  ranking.
- ``AnthropicProvider``, so Claude models can be used as translators,
  validators or judges. Configure an ``"anthropic"`` entry in
  ``TRANSLATIONS_PROVIDERS``.

Fixed
~~~~~
- ``LLMProvider._call_llm`` can now send a request with no ``temperature`` at
  all. Models that removed the parameter rather than restricting its values
  (Claude Opus 5, Sonnet 5, Opus 4.8/4.7) rejected both the requested
  temperature and the 1.0 fallback, so every call to them failed. Whichever
  option a model accepts — including sending none — is memoized per (model,
  requested temperature), so the probing is paid once per process rather than
  on every request.
