OL Open edX AI Static Translations
====================================

An Open edX plugin that provides AI-powered static translation management. It syncs translation keys, translates them using LLM providers, and creates pull requests with translated content.

Purpose
*******

This plugin provides the ``sync_and_translate_language`` management command for syncing and translating Open edX static strings (frontend JSON and backend PO files) using LLM providers (OpenAI, Gemini, Mistral) with optional glossary support.

Setup
=====

For detailed installation instructions, please refer to the `plugin installation guide <../../docs#installation-guide>`_.

Installation required in:

* Studio (CMS)

Configuration
=============

This plugin shares settings with ``ol_openedx_course_translations``. Ensure the following settings are configured:

.. code-block:: python

     TRANSLATIONS_PROVIDERS: {
         "default_provider": "mistral",
         "openai": {"api_key": "", "default_model": "gpt-5.2"},
         "gemini": {"api_key": "", "default_model": "gemini-3-pro-preview"},
         "mistral": {"api_key": "", "default_model": "mistral-large-latest"},
     }
     TRANSLATIONS_GITHUB_TOKEN: <YOUR_GITHUB_TOKEN>  # Personal access token with repo write permissions for creating PRs
     TRANSLATIONS_REPO_PATH: ""  # Local filesystem path where the translations repo will be cloned/checked out
     TRANSLATIONS_REPO_URL: "https://github.com/mitodl/mitxonline-translations.git"  # URL of the remote translations repository

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
- ``--glossary``: Path to glossary directory (optional). Should contain language-specific files (e.g. ``{iso_code}.txt``).
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
        ./manage.py cms sync_and_translate_language el --provider mistral --model mistral-large-latest --glossary /path/to/glossary --batch-size 250

License
*******

The code in this repository is licensed under the BSD 3-Clause license unless
otherwise noted.

Please see `LICENSE.txt <LICENSE.txt>`_ for details.
