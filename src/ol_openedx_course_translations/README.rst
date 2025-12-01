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

Configuration
=============

- Add the following configuration values to the config file in Open edX. For any release after Juniper, that config file is ``/edx/etc/lms.yml``. If you're using ``private.py``, add these values to ``lms/envs/private.py``. These should be added to the top level. **Ask a fellow developer for these values.**

  .. code-block:: python

       DEEPL_API_KEY: <YOUR_DEEPL_API_KEY_HERE>

- For Tutor installations, these values can also be managed through a `custom Tutor plugin <https://docs.tutor.edly.io/tutorials/plugin.html#plugin-development-tutorial>`_.

Usage
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
