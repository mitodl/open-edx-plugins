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

- Add the following configuration values to the config file in Open edX. For any release after Juniper, that config file is ``/edx/etc/lms.yml``. If you're using ``private.py``, add these values to ``lms/envs/private.py``. These should be added to the top level. **Ask a fellow developer for these values.**

  .. code-block:: python

       DEEPL_API_KEY: <YOUR_DEEPL_API_KEY_HERE>
       ENABLE_AUTO_LANGUAGE_SELECTION: true  # Enable auto language selection based on course language

       TRANSLATION_PROVIDERS: {
           "default_provider": "mistral",  # Default provider to use
           "openai": {
               "api_key": "<YOUR_OPENAI_API_KEY>",
               "default_model": "gpt-4",
           },
           "gemini": {
               "api_key": "<YOUR_GEMINI_API_KEY>",
               "default_model": "gemini-pro",
           },
           "mistral": {
               "api_key": "<YOUR_MISTRAL_API_KEY>",
               "default_model": "mistral/mistral-large-latest",
           },
       }
       TRANSLATIONS_GITHUB_TOKEN: <YOUR_GITHUB_TOKEN>
       TRANSLATIONS_REPO_PATH: ""
       TRANSLATIONS_REPO_URL: "https://github.com/mitodl/mitxonline-translations.git"

- For Tutor installations, these values can also be managed through a `custom Tutor plugin <https://docs.tutor.edly.io/tutorials/plugin.html#plugin-development-tutorial>`_.

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

Translating a Course
====================
1. Open the course in Studio.
2. Go to Tools -> Export Course.
3. Export the course as a .tar.gz file.
4. Go to the CMS shell
5. Run the management command to translate the course:

   .. code-block:: bash

        ./manage.py cms translate_course --source-language <SOURCE_LANGUAGE_CODE, defaults to `EN`> --translation-language <TRANSLATION_LANGUAGE_CODE i.e. AR> --course-dir <PATH_TO_EXPORTED_COURSE_TAR_GZ>

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
- ``--provider``: Translation provider (``openai``, ``gemini``, ``mistral``). Default is taken from ``TRANSLATION_PROVIDERS['default_provider']`` setting
- ``--model``: LLM model name. If not specified, uses the ``default_model`` for the selected provider from ``TRANSLATION_PROVIDERS``. Examples: ``gpt-4``, ``gemini-pro``, ``mistral/mistral-large-latest``
- ``--repo-path``: Path to mitxonline-translations repository (can also be set via ``TRANSLATIONS_REPO_PATH`` setting or environment variable)
- ``--repo-url``: GitHub repository URL (default: ``https://github.com/mitodl/mitxonline-translations.git``, can also be set via ``TRANSLATIONS_REPO_URL`` setting or environment variable)
- ``--glossary``: Use glossary from plugin glossaries folder (looks for ``{plugin_dir}/glossaries/machine_learning/{lang_code}.txt``)
- ``--batch-size``: Number of keys to translate per API request (default: 200, recommended: 200-300 for most models)
- ``--mfe``: Filter by specific MFE(s). Use ``edx-platform`` for backend translations
- ``--dry-run``: Run without committing or creating PR

**Examples:**

   .. code-block:: bash

        # Use default provider (from TRANSLATION_PROVIDERS['default_provider']) with its default model
        ./manage.py cms sync_and_translate_language el

        # Use OpenAI provider with its default model (gpt-4)
        ./manage.py cms sync_and_translate_language el --provider openai

        # Use OpenAI provider with a specific model
        ./manage.py cms sync_and_translate_language el --provider openai --model gpt-4-turbo

        # Use Mistral provider with a specific model and glossary
        ./manage.py cms sync_and_translate_language el --provider mistral --model mistral/mistral-small-latest --glossary --batch-size 250

License
*******

The code in this repository is licensed under the AGPL 3.0 unless
otherwise noted.

Please see `LICENSE.txt <LICENSE.txt>`_ for details.
