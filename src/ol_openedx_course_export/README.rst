Course Export S3 Plugin
=============================

A django app plugin to add a new API to Open edX to export courses to S3 buckets.


Installation
------------

For detailed installation instructions, please refer to the `plugin installation guide <../docs#installation-guide>`_.

Installation required in:

* Studio (CMS)

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


.. note::

The API requires JWT authentication. Follow the instructions at `this link <https://docs.openedx.org/projects/edx-platform/en/latest/how-tos/use_the_api.html>`_ to generate a JWT token and use it in the request headers.


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
