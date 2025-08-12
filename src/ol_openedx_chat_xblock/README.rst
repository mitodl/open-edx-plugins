


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

edx-platform configuration
--------------------------

1. Go to the course page in Studio (CMS), open ``Advanced Settings`` and add ``ol_openedx_chat_xblock`` to the ``Advanced module list``.
2. To add this xBlock to a course, you can now select the ``Advanced`` tile on the new unit page and select ``OL Chat xBlock`` from the list of available advanced xBlocks.
3. Add the following configuration values to the config files in Open edX. For any release after Juniper, these config files are ``/edx/etc/lms.yml`` and ``/edx/etc/cms.yml``. If you're using ``private.py``, add these values to ``lms/envs/private.py`` and ``cms/envs/private.py``. These should be added to the top level. **Ask a fellow developer for these values.**

      .. code-block::

        # Required
        MIT_LEARN_AI_XBLOCK_CHAT_API_TOKEN: <MIT_LEARN_AI_XBLOCK_CHAT_API_TOKEN>

        # Required for Syllabus Chat
        MIT_LEARN_AI_XBLOCK_CHAT_API_URL: <MIT_LEARN_AI_XBLOCK_CHAT_API_URL>

        # Required for Tutor Chat
        MIT_LEARN_AI_XBLOCK_TUTOR_CHAT_API_URL: <MIT_LEARN_AI_XBLOCK_TUTOR_CHAT_API_URL>
        MIT_LEARN_AI_XBLOCK_PROBLEM_SET_LIST_URL: <MIT_LEARN_AI_XBLOCK_PROBLEM_SET_LIST_URL>

- For Tutor installations, these values can also be managed through a `custom Tutor plugin <https://docs.tutor.edly.io/tutorials/plugin.html#plugin-development-tutorial>`_.

xBlock configuration
--------------------

- **Course ID Configuration**

  The chat xBlock needs a course ID to work. (NOTE: This is not the course ID of the course xBlock is created in) Here is how the course ID can be set:

  1. Course ID setting in the xBlock in Studio (CMS)
      Just open the chat xBlock settings in Studio (CMS) and set the course ID in the configuration field named `Course ID`.

  2. Auto-generate course ID (LTI Launch Only)
      If you don't set the course ID in the xBlock configuration, the xBlock will automatically try to generate a course ID based on the LTI launch request. This is useful if you want to use the xBlock in multiple courses without having to set the course ID manually.

  Just make sure to add a custom field `course_id=$Canvas.course.id` in Canvas LTI app configuration so that the course ID can be extracted from the LTI launch request.


- **Tutor Configuration**

  The chat xBlock can work as a tutor xBlock as well. Here is how you can set an xBlock to be a tutor xBlock:

  1. Is Tutor setting in the xBlock in Studio (CMS)
      Just open the chat xBlock settings in Studio (CMS) and use the toggle field named `Is Tutor xBlock?`.


Documentation
=============

The chat xBlock enables students to interact with an AI chatbot powered by MIT Learn AI. It provides a user-friendly interface for students to ask questions and receive answers in real-time.

The xBlock provides different features such as:
- Syllabus Chat interface for students to interact with the AI chatbot and receive assistance with syllabus-related queries.
- Tutor Chat interface for students to interact with the AI chatbot and receive assistance with different problems in the courseware.

License
*******

The code in this repository is licensed under the AGPL 3.0 unless
otherwise noted.

Please see `LICENSE.txt <LICENSE.txt>`_ for details.
