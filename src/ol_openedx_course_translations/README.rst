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
- Azure OpenAI (GPT models, authenticated with Entra ID)
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

**Azure OpenAI**

The ``azure`` provider has no API key. It authenticates with an Entra ID token from
``azure.identity.DefaultAzureCredential``, which uses workload identity in Kubernetes
(the ``AZURE_CLIENT_ID``, ``AZURE_TENANT_ID`` and ``AZURE_FEDERATED_TOKEN_FILE``
environment variables) and the Azure CLI login (``az login``) on a laptop.

It is configured with flat settings rather than an entry in ``TRANSLATIONS_PROVIDERS``.
When ``AZURE_OPENAI_ENDPOINT`` is set, the plugin adds an ``azure`` entry to
``TRANSLATIONS_PROVIDERS`` from them and leaves the other providers as they are:

.. code-block:: yaml

    AZURE_OPENAI_ENDPOINT: "https://<account>.openai.azure.com/"
    AZURE_OPENAI_API_VERSION: "2024-10-21"
    AZURE_OPENAI_DEFAULT_DEPLOYMENT: "gpt-5.2"

The model part of an ``azure/<model>`` provider specification is the Azure deployment
name (e.g., ``azure/gpt-5-mini``).

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

``run_translation_benchmark`` answers "which provider should translate this
language, and is it worth running a validator over the result?" with evidence
rather than opinion. It translates a chosen benchmark with every
translator, edits each translation with every validator, has every judge score
the results, and reports a winner.

.. code-block:: bash

    ./manage.py cms run_translation_benchmark \
        --benchmark-block block-v1:Org+Course+Run+type@html+block@abc123 \
        --target-language hi \
        --translators "openai/gpt-5.2,gemini/gemini-3-pro-preview,mistral/mistral-large-latest" \
        --judges "openai/gpt-5.2,anthropic/claude-opus-5"

**Arguments**

- ``--benchmark-block`` (required): usage key of the course block to translate.
  Its published body is the benchmark; nothing ships with the plugin.
- ``--target-language`` (required): must be in ``COURSE_TRANSLATIONS_SUPPORTED_LANGUAGES``.
- ``--translators``: comma-separated ``PROVIDER`` or ``PROVIDER/MODEL`` specs. The same
  roster is used as the validator set, so a run covers every translator/validator
  pairing — ``translators x translators`` candidates. Defaults to every provider
  with an ``api_key``.
- ``--judges``: comma-separated specs that score the candidates. Defaults to every
  provider with an ``api_key``. A provider may be a translator and a judge at once.
- ``--comparative-only``: skip the scoring pass and rank every candidate in one
  call per judge. Turns ``candidates x judges + judges`` judging calls into
  ``judges``, at the cost of the absolute scores, the mean-score column and the
  shortlist. Refuses to run above 26 candidates, the number of anonymous labels
  one comparative call can carry.
- ``--yes``: skip the run-size confirmation.

A roster entry whose provider has no ``api_key`` is skipped with a note rather than
failing the run, so a partly configured environment still produces a comparison.
A provider named on the command line but absent from ``TRANSLATIONS_PROVIDERS`` is
fatal instead — skipping it would answer a different question than the one asked.

The work runs as Celery tasks on the CMS workers, so a large run is not bound
by one process. Each stage is dispatched as a group and awaited before the next
begins; the command prints progress and must stay open for the duration. Tasks
are queued on ``edx.cms.core.low`` because the CMS workers are shared with
course publishing — schedule large runs accordingly.

**What a run does**

1. Translates the benchmark once per translator, reusing that translation across
   all of its validator arms so the arms differ only by validator. The
   unvalidated translation is scaffolding: every validator reads it, then it is
   deleted, so only validated pairings are scored.
2. Runs each validator over each translation. A validator whose output is no
   longer markup is reported and its arm dropped, never scored.
3. Has every judge score every surviving candidate on accuracy, fluency and terminology
   from 1 to 10, one candidate per call.
4. Orders candidates by **mean rank**: each judge's own scores are sorted into
   positions, and those positions are averaged. This gives every judge one equal
   vote regardless of how wide a range it uses. A judge whose reply cannot be
   parsed is dropped from the whole scoring pass, so every candidate is ranked
   over the same set of judges.
5. Sends the leaders — the top five plus anything tied with fifth, capped at
   eight — to a second pass where each judge ranks them side by side,
   anonymized and shuffled per judge. A judge that fails here keeps its scores
   and drops out of the verdict only. With ``--comparative-only`` this is the
   first and only judging pass, and every candidate goes into it.
6. Names the candidate with the lowest mean comparative rank. The verdict
   always comes from the comparative pass — mean rank from the scoring pass
   orders the table and chooses the shortlist, but does not decide the winner.
   A tie at the top is the only refusal, because one pass has no second signal
   to break it.

``--comparative-only`` skips steps 3 and 4 entirely and ranks every candidate
in a single call per judge. That trades ``candidates x judges`` scoring calls
for nothing, at the cost of the absolute scores, the mean-score column and the
shortlist. It refuses to run when the candidates outnumber the 26 anonymous
labels a single comparative call can carry.

**Reading the output**

The table lists every scored candidate with its mean rank, mean score, ``spread``
(the gap between its best and worst position across judges), the number of judges
behind it, and the ``unchanged`` count below. A large spread
means the judges disagreed about that candidate, and is worth more attention
than a small difference in mean rank.

The ``unchanged`` column counts translation units the provider returned identical
to the source. It is a diagnostic, not part of the ranking: some units are
identical in any language, but a high count means the provider skipped content
and the score belongs to a partial translation. In ``--comparative-only`` runs
there is no mean score and the column reads ``—``; ``mean rank`` is then the
mean comparative rank. Arms that failed — a translation
whose every unit came back unchanged, or a validator that returned prose or restructured the
markup — are listed under the table with the reason, so a short table is never a
silent one.

The run records whether the scoring pass was skipped, so the admin renders
the standings as what the run actually was rather than inferring it from the
absence of scores.

Results are stored in ``TranslationBenchmark``, ``TranslationBenchmarkCandidate``
and ``TranslationBenchmarkScore``, and shown in the Django admin. A run can't be
edited there, only deleted as a whole. The run page lists every candidate, its judge scores and the standings, with a column
per judge showing that judge's position, its raw scores and its comparative
rank, and the verdict above the table. A ``--comparative-only`` run recorded
no scores, so those slots read ``—`` and the position is the comparative rank. Each candidate
row keeps the content it was scored on in the database — not shown in the admin
— so a verdict can be checked against the text the judges actually saw.
A judge dropped
from the scoring pass is recorded on the run in ``excluded_judges`` together
with the reason, so a run that rests on fewer judges says so months later.

**The benchmark content**

Nothing is bundled. Point the command at an ``html`` course block and its
published body becomes the benchmark::

    --benchmark-block block-v1:Org+Course+Run+type@html+block@abc123

The published revision is read, not the Studio draft: it is what a course
export contains, so the benchmark measures the same text ``translate_course``
would process, and it does not shift under an author editing in Studio. The
command re-reads the block after creating the run row, so the unchanged-unit
diagnostic is measured against the run's own copy rather than the one the
size estimate was built from.

Each worker process reads the block once per run and reuses it for every task
it runs, which keeps a run from re-reading the course structure hundreds of
times and pins the text that worker measures. The cache key is the run,
which records the block, so a later run never inherits an earlier one's copy. What it does not promise:
workers take their first task at different moments, so a republish *during* a
run still reaches whichever of them has not read yet, and a worker juggling
more runs than it caches re-reads the block for one it evicted.

An html block's body is a fragment with no single root, so it is translated as
HTML — the same ``tag_handling`` production picks from a ``.html`` file
suffix. Only ``html`` blocks are accepted for that reason: a ``problem`` block
has a body too, but it exports as ``.xml``. A block of the wrong type, one
with no markup body, or one whose body has no translatable text, is reported
before anything is spent.

Because the block is live content, two runs naming the same block are only
comparable if nobody republished it in between. The run records the usage key,
not a copy of the text.

The methodology, and the alternatives that were rejected, are recorded in
``docs/adr/0001-translation-quality-benchmark-methodology.md``.

License
*******

The code in this repository is licensed under the AGPL 3.0 unless
otherwise noted.

Please see `LICENSE.txt <LICENSE.txt>`_ for details.
