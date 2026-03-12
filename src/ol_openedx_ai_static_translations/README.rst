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
     TRANSLATIONS_GITHUB_TOKEN: <YOUR_GITHUB_TOKEN>
     TRANSLATIONS_REPO_PATH: ""
     TRANSLATIONS_REPO_URL: "https://github.com/mitodl/mitxonline-translations.git"

Usage
=====

.. code-block:: bash

    # Sync and translate a language
    ./manage.py cms sync_and_translate_language el

    # With specific provider and model
    ./manage.py cms sync_and_translate_language el --provider openai --model gpt-5.2 --glossary

License
*******

The code in this repository is licensed under the AGPL 3.0 unless
otherwise noted.

Please see `LICENSE.txt <LICENSE.txt>`_ for details.
