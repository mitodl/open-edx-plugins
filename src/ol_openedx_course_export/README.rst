Course Export S3 Plugin
=============================

A django app plugin to add a new API to Open edX to export courses to S3 buckets.


Installation
------------

You can install this plugin into any Open edX instance by using any of the following methods:


**Option 1: Install from PyPI**

.. code-block::

    # If running devstack in docker, first open a shell in CMS (make studio-shell)

    pip install ol-openedx-course-export


**Option 2: Build the package locally and install it**

Follow these steps in a terminal on your machine:

1. Navigate to ``open-edx-plugins`` directory
2. If you haven't done so already, run ``./pants build``
3. Run ``./pants package ::``. This will create a "dist" directory inside "open-edx-plugins" directory with ".whl" & ".tar.gz" format packages for all the "ol_openedx_*" plugins in "open-edx-plugins/src")
4. Move/copy any of the ".whl" or ".tar.gz" files for this plugin that were generated in the above step to the machine/container running Open edX (NOTE: If running devstack via Docker, you can use ``docker cp`` to copy these files into your CMS container)
5. Run a shell in the machine/container running Open edX, and install this plugin using pip

Configuration
------------

**1) edx-platform configuration**

You might need to add the following configuration values to the config file in Open edX. For any release after Juniper, that config file is ``/edx/etc/lms.yml``. These should be added to the top level. **Ask a fellow developer or devops for these values.**

.. code-block::


    AWS_ACCESS_KEY_ID: <your aws access id>
    AWS_SECRET_ACCESS_KEY: <your api access key>
    COURSE_IMPORT_EXPORT_BUCKET: <bucket name to export the courses to>


How To Use
----------
The API supports a POST API call that accepts the list of course Ids and returns the uploaded paths of the courses on S3

To call the API, Send a POST request to `<STUDIO_BASE>/api/courses/v0/export/` with the a payload with a list of course IDs that might look like:


.. code-block::


    {
       "courses": ["course-v1:edX+DemoX+Demo_Course"]
    }


The successful response would look like:


.. code-block::

    With 200

    {
        "successful_uploads": {
            "course-v1:edX+DemoX+Demo_Course": "https://bucket_name.s3.amazonaws.com/course-v1:edX+DemoX+Demo_Course.tar.gz",
            "course-v1:edX+Test+Test_Course": "https://bucket_name.s3.amazonaws.com/course-v1:edX+Test+Test_Course.tar.gz"
        },
        "failed_uploads": {}
    }

    With 400

    {
        "successful_uploads": {
            "course-v1:edX+DemoX+Demo_Course": "https://bucket_name.s3.amazonaws.com/course-v1:edX+DemoX+Demo_Course.tar.gz",
        },
        "failed_uploads": {
            "course-v1:edX+Test+Test_Course": "Error message"
        }
    }


The response will contain either the s3 bucket url for successful uploads and/or an error message for failed uploads.
