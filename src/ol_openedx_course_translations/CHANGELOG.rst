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
~~~~~~~~~~

[0.12.0] - 2026-10-06
~~~~~~~~~~~~~~~~~~~~~
Changed
-------
- The benchmark is a course block, named by ``--benchmark-block <usage key>``,
  and the run records that key. The committed fixture is gone, so the package
  carries no course content and the licence question with it. The published
  revision is read, matching what a course export contains.
- Benchmark content is translated as HTML rather than XML. An html block's
  body is a fragment with no single root, and production already picks
  ``tag_handling`` from the file suffix, so the benchmark now measures the
  path production takes instead of an XML-mode approximation. The old
  fixture's ``<html>`` wrapper existed only to satisfy the XML parser. Only
  ``html`` blocks are accepted: a ``problem`` block has a body too, but it
  exports as ``.xml`` and production translates it as XML.
- Only validated pairings are candidates. The unvalidated arm is still
  translated, because every validator reads it, but it is deleted once they
  have and is never scored: a run now compares ``translators x translators``
  arms rather than ``translators x (translators + 1)``. The provider's own
  failure message is copied onto the dependent arms before the source row
  goes, so a failed translation still says why.
- The verdict always comes from the comparative pass. Mean rank from the
  scoring pass orders the standings and picks the shortlist, but the winner
  is the lowest mean comparative rank, declined only on a tie. The previous
  rule required both signals to agree and produced no winner whenever they
  did not.
- New ``--comparative-only`` flag skips the scoring pass and ranks every
  candidate in one call per judge, taking a run from
  ``candidates x judges + judges`` calls down to ``judges``. The standings
  then show mean comparative rank and no mean score. It refuses to start when
  the candidates outnumber the 26 anonymous labels one call can carry, since
  the label mapping would otherwise drop the excess silently.
- ``TranslationQualityScore`` allows null accuracy/fluency/terminology, for
  runs that never scored on the 1-10 scale.
- ``TranslationQualityRun`` records ``comparative_only``, so the console
  report states which passes ran instead of guessing from whether any row
  happened to carry a score. The admin still reads the rows, because it
  renders what a run produced rather than what it intended.
- Benchmark tasks read the block through a cache keyed on the run, which is
  also what they now carry instead of the block id. A 10-translator,
  4-judge run made roughly 500 modulestore reads of the same block, each
  decoding a whole course structure on the queue shared with course
  publishing; it is now about one per worker process per run. A republish
  mid-run no longer splits the arms a single worker produced, and a worker
  warm from an earlier run cannot serve that run's copy to a later one.
  Tasks also address rows scoped to their run, so a call carrying ids from
  another run resolves nothing rather than reading or overwriting a
  finished run's arms.
- An unreadable benchmark block stops a run that has nothing to report yet,
  rather than being recorded as each provider's failure. Once a run holds
  work worth printing it is recorded as that judge's exclusion instead,
  with the block named: the cache is per worker process per run, so one
  cold worker finding the block gone is not grounds to discard a scoring
  pass already paid for.
- Every path that ends a run records why its judges dropped out. The path
  that refuses a run because nothing was ranked never reached the usual
  writer, which was the one case the field had been added for.
- The subtitle system prompt lives on ``LLMProvider`` instead of being copied
  into all four providers. Mistral's extra rule is an override; the prompt each
  provider sends is unchanged, verified byte for byte against the copies.
- ``rate_translation_quality`` dispatches its work as Celery tasks on the CMS
  workers instead of an in-process thread pool. A 10-translator, 4-judge run is
  ~550 calls, which one process serialises into hours; the CMS workers run many
  of them at once. Tasks go to ``edx.cms.core.low``, retry only on ``Timeout``
  and ``RateLimitError``, and each stage is awaited before the next begins.
- ``TranslationQualityRun`` records ``completed_at``. Arms are written as their
  tasks finish, so without it an interrupted run is indistinguishable from a
  finished one in the table it is meant to make comparable over time.
- ``TranslationQualityCandidate`` keeps the content each arm was scored on, so
  tasks address rows by id rather than passing documents through the broker,
  and a stored verdict can be checked against the text behind it.

- Benchmark test coverage is driven by mutation testing rather than by
  reading the tests. The retry, queue and ``propagate=False`` assertions all
  passed while the mechanisms they name were disconnected; they now drive the
  code path instead. ``_dispatch``'s deadline and revoke, the per-judge
  shuffle, the shortlist cut, the majority denominator and the read-only admin
  were untested and are covered.

- The admin standings give each judge its own column — that judge's position,
  its raw accuracy/fluency/terminology, and its comparative rank — and print
  the verdict above the table. When the scoring pass ran, mean rank comes from
  it alone, so a candidate can lead the standings while both judges ranked it
  low head to head; the stored record showed only the flattering half. A
  ``--comparative-only`` run has no scores, so its columns carry ranks alone
  and the legend above the table says so.

Fixed
-----
- A translator whose batch protocol broke is now reported as failed rather
  than scored as bad. ``translate_text`` keeps the original unit whenever a
  reply arrives without its ``:::N:::`` markers and then reserializes, so a
  wholly untranslated document differs from the source — a header comment
  outside the root is dropped, for one — and the byte comparison missed it.
  The gate compares units instead, requiring every unit to be unchanged so
  that units reading identically in any language do not fail a real
  translation.
- A judge reply whose trailing prose contains a brace ("hope that helps :}")
  is parsed instead of rejected. Slicing to the last ``}`` swallowed the prose
  after the object, and a rejected reply drops that judge from the whole
  scoring pass.
- Judging calls are bounded and no longer retried by the provider client.
  Scoring and ranking inherited the configured request timeout (300s for most
  providers) and the client's two retries, so one hang could hold a worker slot
  for 15 minutes. Scoring is now capped at 120s and ranking at 180s, both with
  retries off.
- Validation from the benchmark allows a single 240s attempt rather than three
  90s ones, so a slow-but-working model gets to finish instead of failing three
  times — and slightly under the old 270s worst case.
- Gemini now asks for ``temperature=1.0`` rather than 0.0. Gemini 3 accepts a
  lower value without error and then behaves badly on it — litellm warns it
  "can cause infinite loops, degraded reasoning performance, and failure on
  complex tasks", which showed up as whole-document validation calls hanging
  until they timed out while the smaller chunked translation calls succeeded.
- ``_call_llm`` no longer probes the same temperature twice when a provider
  already asks for the fallback value.

Added
-----
- ``rate_translation_quality`` management command. Translates the chosen benchmark
  with every configured translator, edits each translation with every
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

- ``LLMProvider._call_llm`` can now send a request with no ``temperature`` at
  all. Models that removed the parameter rather than restricting its values
  (Claude Opus 5, Sonnet 5, Opus 4.8/4.7) rejected both the requested
  temperature and the 1.0 fallback, so every call to them failed. Whichever
  option a model accepts — including sending none — is memoized per (model,
  requested temperature), so the probing is paid once per process rather than
  on every request.

[0.11.0] - 2026-09-30
~~~~~~~~~~~~~~~~~~~~~
Added
-----
* ``azure`` translation provider for Azure OpenAI. It sends LiteLLM
  ``azure/<deployment>`` model names and authenticates with an Entra token from
  ``DefaultAzureCredential`` (workload identity in-cluster, ``az login``
  locally), never an API key.
* The flat ``AZURE_OPENAI_ENDPOINT``, ``AZURE_OPENAI_API_VERSION`` and
  ``AZURE_OPENAI_DEFAULT_DEPLOYMENT`` settings are folded into
  ``TRANSLATIONS_PROVIDERS["azure"]`` when ``AZURE_OPENAI_ENDPOINT`` is set.
  This happens in both the common and production settings hooks, because
  production YAML is loaded after the common hook runs.
