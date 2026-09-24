OL Open edX Course Translations
===============================

An Open edX plugin to manage course translations.

Purpose
*******

Translate course content into multiple languages to enhance accessibility for a global audience.

Version Compatibility
======================

For this plugin's compatibility with Open edX, see the
`Open edX Release Compatibility table <../../docs#open-edx-release-compatibility>`_.

Setup
=====

For detailed installation instructions, please refer to the `plugin installation guide <../../docs#installation-guide>`_.

Installation required in:

* Studio (CMS)
* LMS

Configuration
=============

- Add the following configuration values to the config file in Open edX. For any release after Juniper, that config file is ``/edx/etc/lms.yml`` and ``/edx/etc/cms.yml``. If you're using ``private.py``, add these values to ``lms/envs/private.py`` and ``cms/envs/private.py``. These should be added to the top level. **Ask a fellow developer for these values.**

  .. code-block:: python

       # Output directory for translated courses
       # Default: /openedx/data/course_translations/
       COURSE_TRANSLATIONS_BASE_DIR: "/openedx/data/course_translations/"

       # Relative path (within exported course/course/) for course updates JSON
       # where each item's `content` HTML is translated.
       # Default: info/updates.items.json
       COURSE_TRANSLATIONS_UPDATES_ITEMS_JSON_RELATIVE_PATH: "info/updates.items.json"

       # Translation providers configuration
       TRANSLATIONS_PROVIDERS: {
           "default_provider": "mistral",  # Default provider to use
           "openai": {
               "api_key": "<YOUR_OPENAI_API_KEY>",
               "default_model": "gpt-5.2",
           },
           "gemini": {
               "api_key": "<YOUR_GEMINI_API_KEY>",
               "default_model": "gemini-3-pro-preview",
           },
           "mistral": {
               "api_key": "<YOUR_MISTRAL_API_KEY>",
               "default_model": "mistral-large-latest",
           },
       }
       LITE_LLM_REQUEST_TIMEOUT: 300  # Timeout for LLM API requests in seconds

- For Tutor installations, these values can also be managed through a `custom Tutor plugin <https://docs.tutor.edly.io/tutorials/plugin.html#plugin-development-tutorial>`_.

Translation Providers
=====================

The plugin supports multiple translation providers:

- OpenAI (GPT models)
- Gemini (Google)
- Mistral
- Anthropic (Claude models)

**Configuration**

All providers are configured through the ``TRANSLATIONS_PROVIDERS`` dictionary in your settings:

.. code-block:: python

    TRANSLATIONS_PROVIDERS = {
        "default_provider": "mistral",  # Optional: default provider for commands
        "openai": {
            "api_key": "<YOUR_OPENAI_API_KEY>",
            "default_model": "gpt-5.2",  # Optional: used when model not specified
        },
        "gemini": {
            "api_key": "<YOUR_GEMINI_API_KEY>",
            "default_model": "gemini-3-pro-preview",
        },
        "mistral": {
            "api_key": "<YOUR_MISTRAL_API_KEY>",
            "default_model": "mistral-large-latest",
        },
        "anthropic": {
            "api_key": "<YOUR_ANTHROPIC_API_KEY>",
            "default_model": "claude-opus-5",
        },
    }

**Important Notes:**

1. **Default Models**: The ``default_model`` in each provider's configuration is used when you specify a provider without a model (e.g., ``openai`` instead of ``openai/gpt-5.2``).

**Provider Selection**

You can specify providers in two ways:

1. **Provider only** (uses default model from settings):

.. code-block:: bash

    ./manage.py cms translate_course \
        --source-course-id course-v1:TestOrg+Source+Run \
        --target-course-id course-v1:TestOrg+Arabic+Run \
        --target-language ar \
        --content-translation-provider openai \
        --srt-translation-provider gemini

2. **Provider with specific model**:

.. code-block:: bash

    ./manage.py cms translate_course \
        --source-course-id course-v1:TestOrg+Source+Run \
        --target-course-id course-v1:TestOrg+Arabic+Run \
        --target-language ar \
        --content-translation-provider openai/gpt-5.2 \
        --srt-translation-provider gemini/gemini-3-pro-preview

**Note:** If you specify a provider without a model (e.g., ``openai`` instead of ``openai/gpt-5.2``), the system will use the ``default_model`` configured in ``TRANSLATIONS_PROVIDERS`` for that provider.

Translating a Course
====================

The command reads the source course directly from the modulestore, translates its
content, and imports the result into the target course. No manual export or TAR
file handling is required.

1. Open the CMS shell.
2. Run the management command:

   .. code-block:: bash

        ./manage.py cms translate_course \
            --source-course-id course-v1:TestOrg+Source+Run \
            --target-course-id course-v1:TestOrg+Arabic+Run \
            --source-language en \
            --target-language ar \
            --content-translation-provider openai \
            --srt-translation-provider gemini \
            --translation-validation-provider openai/gpt-5.2 \
            --content-glossary /path/to/content/glossary \
            --srt-glossary /path/to/srt/glossary

   The target course is created automatically if it does not already exist.

**Command Options:**

- ``--source-course-id``: Course key of the source course to translate (required). Example: ``course-v1:Org+Course+Run``
- ``--target-course-id``: Course key of the target course to import translated content into (required). The course is created automatically if it does not exist.
- ``--source-language``: Source language code (default: en)
- ``--target-language``: Target language code (required)
- ``--content-translation-provider``: Translation provider for content (XML/HTML and text) (required).

  Format:

  - ``PROVIDER`` - uses provider with default model from settings (e.g., ``openai``, ``gemini``, ``mistral``)
  - ``PROVIDER/MODEL`` - uses provider with specific model (e.g., ``openai/gpt-5.2``, ``gemini/gemini-3-pro-preview``, ``mistral/mistral-large-latest``)

- ``--srt-translation-provider``: Translation provider for SRT subtitles (required). Same format as ``--content-translation-provider``
- ``--translation-validation-provider``: Optional provider to validate/fix XML/HTML translations after translation.
- ``--content-glossary``: Path to glossary directory for content (XML/HTML and text) translation (optional)
- ``--srt-glossary``: Path to glossary directory for SRT subtitle translation (optional)
- ``--batch-size``: Number of translation tasks to run concurrently per batch (optional, default: 20). SRT tasks are still forced to a batch size of 1 when using the Mistral provider, regardless of this setting.

The command also translates ``course/info/updates.items.json`` (or the path
configured in ``COURSE_TRANSLATIONS_UPDATES_ITEMS_JSON_RELATIVE_PATH``) by
translating each update item's ``content`` field as HTML.

**Examples:**

.. code-block:: bash

    # Use OpenAI and Gemini with default models from settings
    ./manage.py cms translate_course \
        --source-course-id course-v1:MyOrg+EnglishCourse+2024 \
        --target-course-id course-v1:MyOrg+FrenchCourse+2024 \
        --target-language fr \
        --content-translation-provider openai \
        --srt-translation-provider gemini

    # Use OpenAI with specific model for content, Gemini with default for subtitles
    ./manage.py cms translate_course \
        --source-course-id course-v1:MyOrg+EnglishCourse+2024 \
        --target-course-id course-v1:MyOrg+FrenchCourse+2024 \
        --target-language fr \
        --content-translation-provider openai/gpt-5.2 \
        --srt-translation-provider gemini

    # Use Mistral with specific model and separate glossaries for content and SRT
    ./manage.py cms translate_course \
        --source-course-id course-v1:MyOrg+EnglishCourse+2024 \
        --target-course-id course-v1:MyOrg+SpanishCourse+2024 \
        --target-language es \
        --content-translation-provider mistral/mistral-large-latest \
        --srt-translation-provider mistral/mistral-large-latest \
        --content-glossary /path/to/content/glossary \
        --srt-glossary /path/to/srt/glossary

    # Use different glossaries for content vs subtitles
    ./manage.py cms translate_course \
        --source-course-id course-v1:MyOrg+EnglishCourse+2024 \
        --target-course-id course-v1:MyOrg+SpanishCourse+2024 \
        --target-language es \
        --content-translation-provider openai \
        --srt-translation-provider gemini \
        --content-glossary /path/to/technical/glossary \
        --srt-glossary /path/to/conversational/glossary

**Glossary Support:**

You can use separate glossaries for content and subtitle translation. This allows you to apply different terminology choices based on context:

- **Content glossary** (``--content-glossary``): Used for XML/HTML content, policy files, ``info/updates.items.json`` HTML content, and text-based course materials. Typically contains more formal or technical terminology.
- **SRT glossary** (``--srt-glossary``): Used for subtitle translation. Can contain more conversational or context-specific terms appropriate for spoken content.

Create language-specific glossary files in each glossary directory:

.. code-block:: bash

    # Content glossary structure
    glossaries/technical/
    ├── ar.txt  # Arabic glossary
    ├── fr.txt  # French glossary
    └── es.txt  # Spanish glossary

    # SRT glossary structure
    glossaries/conversational/
    ├── ar.txt  # Arabic glossary
    ├── fr.txt  # French glossary
    └── es.txt  # Spanish glossary

Format: One term per line as "source_term : translated_term"

.. code-block:: text

    # es HINTS
    ## TERM MAPPINGS
    These are preferred terminology choices for this language. Use them whenever they sound natural; adapt freely if context requires.

    - 'accuracy' : 'exactitud'
    - 'activation function' : 'función de activación'
    - 'artificial intelligence' : 'inteligencia artificial'
    - 'AUC' : 'AUC'

**Note:** Both glossary arguments are optional. If not provided, translation will proceed without glossary terms. You can provide one, both, or neither glossary as needed.

Subtitle Translation and Validation
====================================

The course translation system includes robust subtitle (SRT) translation with automatic validation and retry mechanisms to ensure high-quality translations with preserved timing information.

**Translation Process**

The subtitle translation follows a multi-stage process with built-in quality checks:

1. **Initial Translation**: Subtitles are translated using your configured provider
2. **Validation**: Timestamps, subtitle count, and content are validated to ensure integrity
3. **Automatic Retry**: If validation fails, the system automatically retries translation (up to 1 additional attempt)
4. **Task Failure**: If all retries fail validation, the translation task fails to prevent corrupted subtitle files

**Validation Rules**

The system validates subtitle translations against these criteria:

- **Subtitle Count**: Translated file must have the same number of subtitle blocks as the original
- **Index Matching**: Each subtitle block index must match the original (e.g., if original has blocks 1-100, translation must have blocks 1-100 in the same order)
- **Timestamp Preservation**: Start and end times for each subtitle block must remain unchanged
- **Content Validation**: Non-empty original subtitles must have non-empty translations (blank translations are flagged as errors)

**Example Validation Process:**

.. code-block:: text

    1. Initial Translation (using OpenAI):
       ✓ 150 subtitle blocks translated
       ✗ Validation failed: 3 blocks have mismatched timestamps

    2. Retry Attempt:
       ✓ 150 subtitle blocks translated
       ✗ Validation failed: 2 blocks still have issues

    3. Task Failure:
       ❌ Translation failed after all retries
       ❌ Task aborted to prevent corrupted subtitle files

**Failure Handling**

If subtitle translation fails after all attempts:

- The translation task will fail with a ``ValueError``
- The entire course translation will be aborted to prevent incomplete translations
- The translated course directory will be automatically cleaned up
- An error message will indicate which subtitle file caused the failure
- No partial or corrupted translation files will be left behind

Benchmarking Translation Quality
================================

``rate_translation_quality`` answers "which provider should translate this
language, and is it worth running a validator over the result?" with evidence
rather than opinion. It translates one fixed benchmark unit with every
translator, edits each translation with every validator, has every judge score
the results, and reports a winner.

.. code-block:: bash

    ./manage.py cms rate_translation_quality \
        --target-language hi \
        --translators "openai/gpt-5.2,gemini/gemini-3-pro-preview,mistral/mistral-large-latest" \
        --judges "openai/gpt-5.2,anthropic/claude-opus-5"

**Arguments**

- ``--target-language`` (required): must be in ``COURSE_TRANSLATIONS_SUPPORTED_LANGUAGES``.
- ``--translators``: comma-separated ``PROVIDER`` or ``PROVIDER/MODEL`` specs. The same
  roster is used as the validator set, so a run covers every translator/validator
  pairing plus an unvalidated arm for each translator. Defaults to every provider
  with an ``api_key``.
- ``--judges``: comma-separated specs that score the candidates. Defaults to every
  provider with an ``api_key``. A provider may be a translator and a judge at once.
- ``--yes``: skip the spend confirmation.

A roster entry whose provider has no ``api_key`` is skipped with a note rather than
failing the run, so a partly configured environment still produces a comparison.
A provider named on the command line but absent from ``TRANSLATIONS_PROVIDERS`` is
fatal instead — skipping it would answer a different question than the one asked.

**What a run does**

1. Translates the benchmark once per translator, reusing that translation across
   all of its validator arms so the arms differ only by validator.
2. Runs each validator over each translation. A validator whose output is no
   longer markup is reported and its arm dropped, never scored.
3. Has every judge score every candidate on accuracy, fluency and terminology
   from 1 to 10, one candidate per call.
4. Orders candidates by **mean rank**: each judge's own scores are sorted into
   positions, and those positions are averaged. This gives every judge one equal
   vote regardless of how wide a range it uses. A judge whose reply cannot be
   parsed is dropped from the whole scoring pass, so every candidate is ranked
   over the same set of judges.
5. Sends the leaders — the top five plus anything tied with fifth, capped at
   eight — to a second pass where each judge ranks them side by side,
   anonymized and shuffled per judge. A judge that fails here keeps its scores
   and loses only its first-place vote.
6. Names a winner only when the best mean rank and a majority of first-place
   votes agree. At most one vote counts per judge, and the majority is measured
   against the judges asked to rank, not the ones that answered; otherwise it
   reports both signals and says there is no clear winner.

**Reading the output**

The table lists every candidate with its mean rank, mean score and ``spread``
(the gap between its best and worst position across judges). A large spread
means the judges disagreed about that candidate, and is worth more attention
than a small difference in mean rank.

The ``unchanged`` column counts translation units the provider returned identical
to the source. It is a diagnostic, not part of the ranking: some units are
identical in any language, but a high count means the provider skipped content
and the score belongs to a partial translation. Arms that failed — a translation
that came back unchanged, or a validator that returned prose or restructured the
markup — are listed under the table with the reason, so a short table is never a
silent one.

Results are stored in ``TranslationQualityRun``, ``TranslationQualityCandidate``
and ``TranslationQualityScore``, viewable read-only in the Django admin: the run
page lists every candidate, its judge scores and the standings.

**The benchmark unit**

Every run translates ``ol_openedx_course_translations/benchmarks/benchmark_course_content.xml``.
It is deliberately fixed: scores are only comparable across languages and over
time because the input never changes. Replacing it invalidates comparisons with
earlier runs.

The methodology, and the alternatives that were rejected, are recorded in
``docs/adr/0001-translation-quality-benchmark-methodology.md``.

License
*******

The code in this repository is licensed under the AGPL 3.0 unless
otherwise noted.

Please see `LICENSE.txt <LICENSE.txt>`_ for details.
