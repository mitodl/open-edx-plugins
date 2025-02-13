Course Structure API Plugin
=============================

A django app plugin to add a new API to Open edX to retrieve the JSON representation of course structure


Installation
------------

For detailed installation instructions, please refer to the `plugin installation guide <../docs#installation-guide>`_.

Installation required in:

* LMS

How To Use
----------
The API supports a GET API call with two optional query parameters
 - ``inherited_metadata`` : include inherited metadata at course level (default to false)
 - ``inherited_metadata_default``: include default values of inherited metadata (default to false)

To call the API, it requires superuser account for GET request to ``<LMS_BASE>/api/courses/v0/<course_id>/``:

The successful response for ``http://localhost:18000/api/course-structure/v0/course-v1:edX+DemoX+Demo_Course/`` would look like:

.. code-block::

     {
            "block-v1:edX+DemoX+Demo_Course+type@chapter+block@1414ffd5143b4b5": {
                "category": "chapter"
                "children": [
                             "block-v1:edX+DemoX+Demo_Course+type@chapter+block@d8a6192ade314473a78242dfeedfbf5b",
                             "block-v1:edX+DemoX+Demo_Course+type@chapter+block@interactive_demonstrations",
                             "block-v1:edX+DemoX+Demo_Course+type@chapter+block@graded_interactions"
                            ]
                 "metadata": {"display_name":"Example Week 1: Getting Started"}
           },
            "block-v1:edX+DemoX+Demo_Course+type@chapter+block@d8a6192ade314473a": {
                "category": "chapter"
                "children": ["block-v1:edX+DemoX+Demo_Course+type@sequential+block@edx_introduction"]
                "metadata": {"display_name":"Example Week 2: Get Interactive"}
           },
    }


The successful response for ``http://localhost:18000/api/course-structure/v0/course-v1:edX+DemoX+Demo_Course/?inherited_metadata=true&inherited_metadata_default=true`` would look like:
.. code-block::

     {
            "block-v1:edX+DemoX+Demo_Course+type@chapter+block@1414ffd5143b4b5": {
                "category": "chapter"
                "children": [
                             "block-v1:edX+DemoX+Demo_Course+type@chapter+block@d8a6192ade314473a78242dfeedfbf5b",
                             "block-v1:edX+DemoX+Demo_Course+type@chapter+block@interactive_demonstrations",
                             "block-v1:edX+DemoX+Demo_Course+type@chapter+block@graded_interactions"
                             ]
                 "inherited_metadata": {
                           "name":null,
                           "course_edit_method":"Studio",
                           "graceperiod":"18000 seconds",
                           "graded": false,
                            ----
                           "self_paced":false,
                           "start":"2013-02-05T05:00:00Z",
                           "xqa_key":"qaijS3UatK020Wc0sfCtFe0V6jpB4d64"
                           }
                 "metadata": {"display_name":"Example Week 1: Getting Started"}
             },
            "block-v1:edX+DemoX+Demo_Course+type@chapter+block@d8a6192ade314473a": {
                "category": "chapter"
                "children": ["block-v1:edX+DemoX+Demo_Course+type@sequential+block@edx_introduction"]
                "inherited_metadata": {
                           "name":null,
                           "course_edit_method":"Studio",
                           "graceperiod":"18000 seconds",
                           "graded": false,
                            ----
                           "self_paced":false,
                           "start":"2013-02-05T05:00:00Z",
                            "xqa_key":"qaijS3UatK020Wc0sfCtFe0V6jpB4d64"
                           }
                "metadata": {"display_name":"Example Week 2: Get Interactive"}
           },
     }
