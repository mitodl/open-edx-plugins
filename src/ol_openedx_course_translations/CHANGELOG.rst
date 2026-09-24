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

Fixed
~~~~~
- ``rate_translation_quality``: a judge's failure reason, and the reason an arm
  dropped out, are now reported instead of discarded — a short standings table
  is never a silent one.
- A judge that ties two candidates for first place no longer casts two
  first-place votes, and the majority is measured against the judges *asked* to
  rank rather than the ones that answered, so one surviving judge out of five
  can no longer carry a "majority".
- Validator output whose element count differs from its input is rejected:
  ``validate_translation`` is told to change no markup, so a change means the
  document being scored is not the one that was translated.
- The standings are printed before they are persisted, so a write failure does
  not discard a run that cost money.
- The admin standings table rendered by ``TranslationQualityRunAdmin.report``
  raised ``TypeError`` on every call (``format_html`` with no interpolation
  arguments, then a numeric format spec applied to an escaped ``SafeString``).
- Translation units the provider handed back unchanged are counted and shown,
  so a partially translated document is no longer scored as if a low result
  were the model's judgement.

[0.11.0] - 2026-09-24
---------------------

Added
~~~~~
- ``rate_translation_quality`` management command. Translates a fixed benchmark
  unit with every configured translator, edits each translation with every
  validator (keeping an unvalidated arm), has every judge score the results,
  and reports which translator/validator pairing wins. Results are stored in
  ``TranslationQualityRun``, ``TranslationQualityCandidate`` and
  ``TranslationQualityScore``, and readable in the Django admin.
- ``AnthropicProvider``, so Claude models can be used as translators,
  validators or judges. Configure an ``"anthropic"`` entry in
  ``TRANSLATIONS_PROVIDERS``.

[0.10.1] - 2026-09-24
---------------------

Fixed
~~~~~
- ``LLMProvider._call_llm`` can now send a request with no ``temperature`` at
  all. Models that removed the parameter rather than restricting its values
  (Claude Opus 5, Sonnet 5, Opus 4.8/4.7) rejected both the requested
  temperature and the 1.0 fallback, so every call to them failed. Whichever
  option a model accepts — including sending none — is memoized per (model,
  requested temperature), so the probing is paid once per process rather than
  on every request.
