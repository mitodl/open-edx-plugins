OL Open edX Course Translations
===============================

An Open edX plugin to manage course translations.

Purpose
*******

Translate course content into multiple languages to enhance accessibility for a global audience.

Setup
=====

For detailed installation instructions, please refer to the `plugin installation guide <../../docs#installation-guide>`_.

Installation required in:

* Studio (CMS)
* LMS (for auto language selection feature)

Configuration
=============

- Add the following configuration values to the config file in Open edX. For any release after Juniper, that config file is ``/edx/etc/lms.yml`` and ``/edx/etc/cms.yml``. If you're using ``private.py``, add these values to ``lms/envs/private.py`` and ``cms/envs/private.py``. These should be added to the top level. **Ask a fellow developer for these values.**

  .. code-block:: python

       # Enable auto language selection
       ENABLE_AUTO_LANGUAGE_SELECTION: true

       # Translation providers configuration
       TRANSLATIONS_PROVIDERS: {
           "default_provider": "mistral",  # Default provider to use
           "deepl": {
               "api_key": "<YOUR_DEEPL_API_KEY>",
           },
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
       TRANSLATIONS_GITHUB_TOKEN: <YOUR_GITHUB_TOKEN>
       TRANSLATIONS_REPO_PATH: ""
       TRANSLATIONS_REPO_URL: "https://github.com/mitodl/mitxonline-translations.git"
       LITE_LLM_REQUEST_TIMEOUT: 300  # Timeout for LLM API requests in seconds

- For Tutor installations, these values can also be managed through a `custom Tutor plugin <https://docs.tutor.edly.io/tutorials/plugin.html#plugin-development-tutorial>`_.

Translation Providers
=====================

The plugin supports multiple translation providers:

- DeepL
- OpenAI (GPT models)
- Gemini (Google)
- Mistral

**Configuration**

All providers are configured through the ``TRANSLATIONS_PROVIDERS`` dictionary in your settings:

.. code-block:: python

    TRANSLATIONS_PROVIDERS = {
        "default_provider": "mistral",  # Optional: default provider for commands
        "deepl": {
            "api_key": "<YOUR_DEEPL_API_KEY>",
        },
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
    }

**Important Notes:**

1. **DeepL Configuration**: DeepL must be configured in ``TRANSLATIONS_PROVIDERS['deepl']['api_key']``.

2. **DeepL for Subtitle Repair**: DeepL is used as a fallback repair mechanism for subtitle translations when LLM providers fail validation. Even if you use LLM providers for primary translation, you should configure DeepL to enable automatic repair.

3. **Default Models**: The ``default_model`` in each provider's configuration is used when you specify a provider without a model (e.g., ``openai`` instead of ``openai/gpt-5.2``).

**Provider Selection**

You can specify providers in three ways:

1. **Provider only** (uses default model from settings):

.. code-block:: bash

    ./manage.py cms translate_course \
        --target-language AR \
        --course-dir /path/to/course.tar.gz \
        --content-translation-provider openai \
        --srt-translation-provider gemini

2. **Provider with specific model**:

.. code-block:: bash

    ./manage.py cms translate_course \
        --target-language AR \
        --course-dir /path/to/course.tar.gz \
        --content-translation-provider openai/gpt-5.2 \
        --srt-translation-provider gemini/gemini-3-pro-preview

3. **DeepL** (no model needed):

.. code-block:: bash

    ./manage.py cms translate_course \
        --target-language AR \
        --course-dir /path/to/course.tar.gz \
        --content-translation-provider deepl \
        --srt-translation-provider deepl

**Note:** If you specify a provider without a model (e.g., ``openai`` instead of ``openai/gpt-5.2``), the system will use the ``default_model`` configured in ``TRANSLATIONS_PROVIDERS`` for that provider.

Translating a Course
====================
1. Open the course in Studio.
2. Go to Tools -> Export Course.
3. Export the course as a .tar.gz file.
4. Go to the CMS shell
5. Run the management command to translate the course:

   .. code-block:: bash

        ./manage.py cms translate_course \
            --source-language EN \
            --target-language AR \
            --course-dir /path/to/course.tar.gz \
            --content-translation-provider openai \
            --srt-translation-provider gemini \
            --translation-validation-provider openai/gpt-5.2 \
            --content-glossary /path/to/content/glossary \
            --srt-glossary /path/to/srt/glossary

**Command Options:**

- ``--source-language``: Source language code (default: EN)
- ``--target-language``: Target language code (required)
- ``--course-dir``: Path to exported course tar.gz file (required)
- ``--content-translation-provider``: Translation provider for content (XML/HTML and text) (required).

  Format:

  - ``deepl`` - uses DeepL (no model needed)
  - ``PROVIDER`` - uses provider with default model from settings (e.g., ``openai``, ``gemini``, ``mistral``)
  - ``PROVIDER/MODEL`` - uses provider with specific model (e.g., ``openai/gpt-5.2``, ``gemini/gemini-3-pro-preview``, ``mistral/mistral-large-latest``)

- ``--srt-translation-provider``: Translation provider for SRT subtitles (required). Same format as ``--content-translation-provider``
- ``--translation-validation-provider``: Optional provider to validate/fix XML/HTML translations after translation.
- ``--content-glossary``: Path to glossary directory for content (XML/HTML and text) translation (optional)
- ``--srt-glossary``: Path to glossary directory for SRT subtitle translation (optional)

**Examples:**

.. code-block:: bash

    # Use DeepL for both content and subtitles
    ./manage.py cms translate_course \
        --target-language AR \
        --course-dir /path/to/course.tar.gz \
        --content-translation-provider deepl \
        --srt-translation-provider deepl

    # Use OpenAI and Gemini with default models from settings
    ./manage.py cms translate_course \
        --target-language FR \
        --course-dir /path/to/course.tar.gz \
        --content-translation-provider openai \
        --srt-translation-provider gemini

    # Use OpenAI with specific model for content, Gemini with default for subtitles
    ./manage.py cms translate_course \
        --target-language FR \
        --course-dir /path/to/course.tar.gz \
        --content-translation-provider openai/gpt-5.2 \
        --srt-translation-provider gemini

    # Use Mistral with specific model and separate glossaries for content and SRT
    ./manage.py cms translate_course \
        --target-language ES \
        --course-dir /path/to/course.tar.gz \
        --content-translation-provider mistral/mistral-large-latest \
        --srt-translation-provider mistral/mistral-large-latest \
        --content-glossary /path/to/content/glossary \
        --srt-glossary /path/to/srt/glossary

    # Use different glossaries for content vs subtitles
    ./manage.py cms translate_course \
        --target-language AR \
        --course-dir /path/to/course.tar.gz \
        --content-translation-provider openai \
        --srt-translation-provider gemini \
        --content-glossary /path/to/technical/glossary \
        --srt-glossary /path/to/conversational/glossary

**Glossary Support:**

You can use separate glossaries for content and subtitle translation. This allows you to apply different terminology choices based on context:

- **Content glossary** (``--content-glossary``): Used for XML/HTML content, policy files, and text-based course materials. Typically contains more formal or technical terminology.
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

    # ES HINTS
    ## TERM MAPPINGS
    These are preferred terminology choices for this language. Use them whenever they sound natural; adapt freely if context requires.

    - 'accuracy' : 'exactitud'
    - 'activation function' : 'función de activación'
    - 'artificial intelligence' : 'inteligencia artificial'
    - 'AUC' : 'AUC'

**Note:** Both glossary arguments are optional. If not provided, translation will proceed without glossary terms. You can provide one, both, or neither glossary as needed.

Subtitle Translation and Validation
====================================

The course translation system includes robust subtitle (SRT) translation with automatic validation and repair mechanisms to ensure high-quality translations with preserved timing information.

**Translation Process**

The subtitle translation follows a multi-stage process with built-in quality checks:

1. **Initial Translation**: Subtitles are translated using your configured provider (DeepL or LLM)
2. **Validation**: Timestamps, subtitle count, and content are validated to ensure integrity
3. **Automatic Retry**: If validation fails, the system automatically retries translation (up to 1 additional attempt)
4. **DeepL Repair Fallback**: If retries fail, the system automatically falls back to DeepL for repair

**Why DeepL for Repair?**

When subtitle translations fail validation (mismatched timestamps, incorrect subtitle counts, or blank translations), the system automatically uses **DeepL as a repair mechanism**, regardless of which provider was initially used. This design choice is based on extensive testing and production experience:

- **Higher Reliability**: LLMs frequently fail to preserve subtitle structure and timestamps correctly, even with detailed prompting
- **Consistent Formatting**: DeepL's specialized subtitle translation API maintains timing precision through XML tag handling
- **Lower Failure Rate**: DeepL demonstrates significantly better success rates for subtitle translation compared to LLMs
- **Timestamp Preservation**: DeepL's built-in XML tag handling ensures start and end times remain intact during translation


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

    3. DeepL Repair:
       ✓ 150 subtitle blocks retranslated using DeepL
       ✓ Validation passed: All timestamps and content validated
       ✅ Translation completed successfully

**Failure Handling**

If subtitle repair fails after all attempts (including DeepL fallback):

- The translation task will fail with a ``ValueError``
- The entire course translation will be aborted to prevent incomplete translations
- The translated course directory will be automatically cleaned up
- An error message will indicate which subtitle file caused the failure
- No partial or corrupted translation files will be left behind

Auto Language Selection
=======================

The plugin includes an auto language selection feature that automatically sets the user's language preference based on the course language. When enabled, users will see the static site content in the course's configured language.

To enable auto language selection:

1. Set ``ENABLE_AUTO_LANGUAGE_SELECTION`` to ``true`` in your settings.

2. Set ``SHARED_COOKIE_DOMAIN`` to your domain (e.g., ``.local.openedx.io`` for local tutor setup) to allow cookies to be shared between LMS and CMS.

**How it works:**

- **LMS**: The ``CourseLanguageCookieMiddleware`` automatically detects course URLs and sets the language preference based on the course's configured language.
- **CMS**: The ``CourseLanguageCookieResetMiddleware`` ensures Studio always uses English for the authoring interface.
- **Admin areas**: Admin URLs (``/admin``, ``/sysadmin``, instructor dashboards) are forced to use English regardless of course language.

MFE Integration
===============

To make auto language selection work with Micro-Frontends (MFEs), you need to use a custom Footer component that handles language detection and switching.

**Setup:**

1. Use the Footer component from `src/bridge/settings/openedx/mfe/slot_config/Footer.jsx <https://github.com/mitodl/ol-infrastructure/blob/main/src/bridge/settings/openedx/mfe/slot_config/Footer.jsx>`_ in the `ol-infrastructure <https://github.com/mitodl/ol-infrastructure>`_ repository.

2. Enable auto language selection in each MFE by adding the following to their ``.env.development`` file:

   .. code-block:: bash

       ENABLE_AUTO_LANGUAGE_SELECTION="true"

3. This custom Footer component:
   - Detects the current course context in MFEs
   - Automatically switches the MFE language based on the course's configured language
   - Ensures consistent language experience across the platform

4. Configure your MFE slot overrides to use this custom Footer component instead of the default one.

**Note:** The custom Footer is required because MFEs run as separate applications and need their own mechanism to detect and respond to course language settings. The environment variable must be set in each MFE's configuration for the feature to work properly.

Generating static content translations
======================================

This command synchronizes translation keys from edx-platform and MFE's, translates empty keys using LLM, and automatically creates a pull request in the translations repository.

**What it does:**

1. Syncs translation keys from edx-platform and MFE's to the translations repository
2. Extracts empty translation keys that need translation
3. Translates empty keys using the specified LLM provider and model
4. Applies translations to JSON and PO files
5. Commits changes to a new branch
6. Creates a pull request with translation statistics

**Usage:**

1. Go to the CMS shell
2. Run the management command:

   .. code-block:: bash

        ./manage.py cms sync_and_translate_language <LANGUAGE_CODE> [OPTIONS]

**Required arguments:**

- ``LANGUAGE_CODE``: Language code (e.g., ``el``, ``fr``, ``es_ES``)

**Optional arguments:**

- ``--iso-code``: ISO code for JSON files (default: same as language code)
- ``--provider``: Translation provider (``openai``, ``gemini``, ``mistral``). Default is taken from ``TRANSLATIONS_PROVIDERS['default_provider']`` setting
- ``--model``: LLM model name. If not specified, uses the ``default_model`` for the selected provider from ``TRANSLATIONS_PROVIDERS``. Examples: ``gpt-5.2``, ``gemini-3-pro-preview``, ``mistral-large-latest``
- ``--repo-path``: Path to mitxonline-translations repository (can also be set via ``TRANSLATIONS_REPO_PATH`` setting or environment variable)
- ``--repo-url``: GitHub repository URL (default: ``https://github.com/mitodl/mitxonline-translations.git``, can also be set via ``TRANSLATIONS_REPO_URL`` setting or environment variable)
- ``--glossary``: Use glossary from plugin glossaries folder (looks for ``{plugin_dir}/glossaries/machine_learning/{lang_code}.txt``)
- ``--batch-size``: Number of keys to translate per API request (default: 200, recommended: 200-300 for most models)
- ``--mfe``: Filter by specific MFE(s). Use ``edx-platform`` for backend translations
- ``--dry-run``: Run without committing or creating PR

**Examples:**

   .. code-block:: bash

        # Use default provider (from TRANSLATIONS_PROVIDERS['default_provider']) with its default model
        ./manage.py cms sync_and_translate_language el

        # Use OpenAI provider with its default model (gpt-5.2)
        ./manage.py cms sync_and_translate_language el --provider openai

        # Use OpenAI provider with a specific model
        ./manage.py cms sync_and_translate_language el --provider openai --model gpt-5.2

        # Use Mistral provider with a specific model and glossary
        ./manage.py cms sync_and_translate_language el --provider mistral --model mistral-large-latest --glossary --batch-size 250

License
*******

The code in this repository is licensed under the AGPL 3.0 unless
otherwise noted.

Please see `LICENSE.txt <LICENSE.txt>`_ for details.
