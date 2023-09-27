Course Structure API Plugin
=============================

A django app plugin to add a new API to Open edX to retrieve the JSON representation of course structure


Installation
------------

You can install this plugin into any Open edX instance by using any of the following methods:


**Option 1: Install from PyPI**

.. code-block::

    # run it in LMS container
    pip install ol-openedx-course-structure-api


**Option 2: Build the package locally and install it**

Follow these steps in a terminal on your machine:

1. Navigate to ``open-edx-plugins`` directory
2. If you haven't done so already, run ``./pants build``
3. Run ``./pants package ::``. This will create a "dist" directory inside "open-edx-plugins" directory with ".whl" & ".tar.gz" format packages for all the "ol_openedx_*" plugins in "open-edx-plugins/src")

If running devstack, do the following 4 and 5 steps:

4. Move/copy any of the ".whl" or ".tar.gz" files for this plugin that were generated in the above step to the machine/container running Open edX (NOTE: you can use docker cp to copy these files into your LMS container)
5. Run a shell in the machine/container running Open edX, and install this plugin using pip

If running tutor, do the following few steps:

4. Extract ".tar.gz" file (e.g. tar command)
5. Move the above extracted files to ``env/build/openedx/requirements/`` in tutor
6. Create/Edit ``env/build/openedx/requirements/private.txt`` with this plugin files

.. code-block::

   -e ./ol-openedx-course-structure-api-0.1.0/

7. Run ``tutor images build openedx``
8. Run ``tutor local run lms ./manage.py lms print_setting INSTALLED_APPS`` to confirm the plugin is installed
9. Restart tutor ``tutor local start``

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
