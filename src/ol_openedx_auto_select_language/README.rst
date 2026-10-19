OL Open edX Auto Select Language
================================

An Open edX plugin to auto select the Open edX platform language based on the course language.

Purpose
*******

Auto select the Open edX platform language based on the course language. When enabled, users will see the static site content in the course's configured language.

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

       # Enable auto language selection
       ENABLE_AUTO_LANGUAGE_SELECTION: true

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

Video Transcript Languages
==========================

When ``ENABLE_AUTO_LANGUAGE_SELECTION`` is true, the LMS video player offers
only the course-language transcript; its language menu is not rendered.

This is implemented as a ``VerticalBlockChildRenderStarted`` pipeline step
(``org.openedx.learning.vertical_block_child.render.started.v1``) that narrows
the language list each video block hands to the player. Transcript downloads,
the ``available_translations`` handler, the mobile ``student_view_data``
payload and Studio are unaffected, so course teams continue to manage every
uploaded language.

The course language is read from the course, not from the transcript the
player resolved. If a video has no transcript in the course language, the
player keeps its full language menu rather than being pinned to whichever
transcript the platform happened to fall back to.

Videos rendered outside a vertical -- a direct ``render_xblock`` on a video
usage key, or the public video sharing page -- are not covered, because the
filter only fires for children of a vertical block.

License
*******

The code in this repository is licensed under the AGPL 3.0 unless
otherwise noted.

Please see `LICENSE.txt <LICENSE.txt>`_ for details.
