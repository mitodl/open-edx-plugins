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

       # Required API keys
       DEEPL_API_KEY: <YOUR_DEEPL_API_KEY_HERE>

       # Enable auto language selection
       ENABLE_AUTO_LANGUAGE_SELECTION: true

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
       TRANSLATIONS_GITHUB_TOKEN: <YOUR_GITHUB_TOKEN>
       TRANSLATIONS_REPO_PATH: ""
       TRANSLATIONS_REPO_URL: "https://github.com/mitodl/mitxonline-translations.git"

       **Note:** DeepL uses the ``DEEPL_API_KEY`` setting directly. LLM providers (OpenAI, Gemini, Mistral) use the ``TRANSLATIONS_PROVIDERS`` dictionary for configuration.

- For Tutor installations, these values can also be managed through a `custom Tutor plugin <https://docs.tutor.edly.io/tutorials/plugin.html#plugin-development-tutorial>`_.

Translation Providers
=====================

The plugin supports multiple translation providers:

- DeepL
- OpenAI (GPT models)
- Gemini (Google)
- Mistral

**Provider Selection**

You can specify different providers for content and SRT subtitle translation using the format ``PROVIDER/MODEL``:

.. code-block:: bash

    ./manage.py cms translate_course \
        --target-language AR \
        --course-dir /path/to/course.tar.gz \
        --content-translation-provider openai/gpt-5.2 \
        --srt-translation-provider gemini/gemini-3-pro-preview

For DeepL, just specify ``deepl`` without a model:

.. code-block:: bash

    ./manage.py cms translate_course \
        --target-language AR \
        --course-dir /path/to/course.tar.gz \
        --content-translation-provider deepl \
        --srt-translation-provider deepl

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
            --content-translation-provider openai/gpt-5.2 \
            --srt-translation-provider gemini/gemini-3-pro-preview \
            --glossary-dir /path/to/glossary

**Command Options:**

- ``--source-language``: Source language code (default: EN)
- ``--target-language``: Target language code (required)
- ``--course-dir``: Path to exported course tar.gz file (required)
- ``--content-translation-provider``: Translation provider for content (XML/HTML and text) (required). Format: ``deepl`` or ``PROVIDER/MODEL`` (e.g., ``openai/gpt-5.2``, ``gemini/gemini-3-pro-preview``, ``mistral/mistral-large-latest``)
- ``--srt-translation-provider``: Translation provider for SRT subtitles (required). Format: ``deepl`` or ``PROVIDER/MODEL`` (e.g., ``openai/gpt-5.2``, ``gemini/gemini-3-pro-preview``, ``mistral/mistral-large-latest``)
- ``--glossary-dir``: Path to glossary directory (optional)

**Examples:**

.. code-block:: bash

    # Use DeepL for both content and subtitles
    ./manage.py cms translate_course \
        --target-language AR \
        --course-dir /path/to/course.tar.gz \
        --content-translation-provider deepl \
        --srt-translation-provider deepl

    # Use OpenAI GPT-5.2 for content and Gemini for subtitles
    ./manage.py cms translate_course \
        --target-language FR \
        --course-dir /path/to/course.tar.gz \
        --content-translation-provider openai/gpt-5.2 \
        --srt-translation-provider gemini/gemini-3-pro-preview

    # Use Mistral with glossary
    ./manage.py cms translate_course \
        --target-language ES \
        --course-dir /path/to/course.tar.gz \
        --content-translation-provider mistral/mistral-large-latest \
        --srt-translation-provider mistral/mistral-large-latest \
        --glossary-dir /path/to/glossary

**Glossary Support:**

Create language-specific glossary files in the glossary directory:

.. code-block:: bash

    glossaries/machine_learning/
    ├── ar.txt  # Arabic glossary
    ├── fr.txt  # French glossary
    └── es.txt  # Spanish glossary

Format: One term per line as "source_term : translated_term"

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
