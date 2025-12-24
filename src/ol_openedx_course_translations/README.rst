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

License
*******

The code in this repository is licensed under the AGPL 3.0 unless
otherwise noted.

Please see `LICENSE.txt <LICENSE.txt>`_ for details.
