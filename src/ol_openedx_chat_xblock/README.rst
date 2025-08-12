


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
- Go to the course page in Studio (CMS), open ``Advanced Settings`` and add ``ol_openedx_chat_xblock`` to the ``Advanced module list``.
- To add this xBlock to a course, you can now select the ``Advanced`` tile on the new unit page and select ``OL Chat xBlock`` from the list of available advanced xBlocks.
- Add the following configuration values to the config file in Open edX. For any release after Juniper, that config file is ``/edx/etc/lms.yml``. If you're using ``private.py``, add these values to ``lms/envs/private.py``. These should be added to the top level. **Ask a fellow developer for these values.**

  .. code-block::

    MIT_LEARN_AI_XBLOCK_CHAT_API_URL: <MIT_LEARN_AI_XBLOCK_CHAT_API_URL>
    MIT_LEARN_AI_XBLOCK_CHAT_API_TOKEN: <MIT_LEARN_AI_XBLOCK_CHAT_API_TOKEN>
    
    ## Required only if you want to use the Tutor Chat interface.
    MIT_LEARN_AI_XBLOCK_TUTOR_CHAT_API_URL: <MIT_LEARN_AI_XBLOCK_TUTOR_CHAT_API_URL>
    MIT_LEARN_AI_XBLOCK_PROBLEM_SET_LIST_URL: <MIT_LEARN_AI_XBLOCK_PROBLEM_SET_LIST_URL>

- For Tutor installations, these values can also be managed through a `custom Tutor plugin <https://docs.tutor.edly.io/tutorials/plugin.html#plugin-development-tutorial>`_.

1. xBlock configuration
------------------------
The chat xBlock needs a course Id to work and that course ID can be set in two ways:

1. By setting the course ID in the xBlock configuration in Studio (CMS)
   Just open the chat xBlock settings in Studio (CMS) and set the course ID in the configuration field named `Course ID`.
2. Auto generate course ID (LTI Launch Only)
   If you don't set the course ID in the xBlock configuration, the xBlock will automatically try generate a course ID based on the LTI launch request. This is useful if you want to use the xBlock in multiple courses without having to set the course ID manually.
   Just make sure to add a custom field `course_id=$Canvas.course.id` in Canvas LTI app configuration so that the course ID can be extracted from the LTI launch request.


Documentation
=============

The chat xBlock enables students to interact with an AI chatbot powered by. It provides a user-friendly interface for students to ask questions and receive answers in real-time.

The xBlock provides different features such as:
- Syllabus Chat interface for students to interact with the AI chatbot and receive assistance with syllabus-related queries.
- Tutor Chat interface for students to interact with the AI chatbot and receive assistance with different problems in the courseware.

License
*******

The code in this repository is licensed under the AGPL 3.0 unless
otherwise noted.

Please see `LICENSE.txt <LICENSE.txt>`_ for details.
