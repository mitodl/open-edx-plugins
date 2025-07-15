


OL OpenedX Chat xBlock
######################

An xBlock to add MIT Open Learning chat in courses.


Purpose
*******

MIT's AI chatbot xBlock for Open edX

Setup
=====

For detailed installation instructions, please refer to the `plugin installation guide <../../docs#installation-guide>`_.

Installation required in:

* LMS
* Studio (CMS)

Configuration
=============

1. edx-platform configuration
-----------------------------

- Add the following configuration values to the config file in Open edX. For any release after Juniper, that config file is ``/edx/etc/lms.yml``. If you're using ``private.py``, add these values to ``lms/envs/private.py``. These should be added to the top level. **Ask a fellow developer for these values.**

  .. code-block::

    MIT_LEARN_AI_XBLOCK_CHAT_API_URL: <MIT_LEARN_AI_XBLOCK_CHAT_API_URL>
    MIT_LEARN_AI_XBLOCK_CHAT_API_TOKEN: <MIT_LEARN_AI_XBLOCK_CHAT_API_TOKEN>

- For Tutor installations, these values can also be managed through a `custom Tutor plugin <https://docs.tutor.edly.io/tutorials/plugin.html#plugin-development-tutorial>`_.


Documentation
=============

License
*******

The code in this repository is licensed under the AGPL 3.0 unless
otherwise noted.

Please see `LICENSE.txt <LICENSE.txt>`_ for details.
