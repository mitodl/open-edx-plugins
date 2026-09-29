Course Export S3 Plugin
=============================

A django app plugin to add a new API to Open edX to export courses to S3 buckets.


Version Compatibility
----------------------

For this plugin's compatibility with Open edX, see the
`Open edX Release Compatibility table <../../docs#open-edx-release-compatibility>`_.

Installation
------------

For detailed installation instructions, please refer to the `plugin installation guide <../../docs#installation-guide>`_.

Installation required in:

* Studio (CMS)

Configuration
-------------

**1) edx-platform configuration**

- You might need to add the following configuration values to the config file in Open edX. For any release after Juniper, that config file is ``/edx/etc/cms.yml``. If you're using ``private.py``, add these values to ``cms/envs/private.py``. These should be added to the top level. **Ask a fellow developer or devops for these values.**

  .. code-block::


    AWS_ACCESS_KEY_ID: <your aws access id>
    AWS_SECRET_ACCESS_KEY: <your api access key>
    COURSE_IMPORT_EXPORT_BUCKET: <bucket name to export the courses to>

- For Tutor installations, these values can also be managed through a `custom tutor plugin <https://docs.tutor.edly.io/tutorials/plugin.html#plugin-development-tutorial>`_.

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


Content versions
~~~~~~~~~~~~~~~~

A course's published version only moves when modulestore content is published.
Files uploaded to the course and transcripts uploaded through VAL never move it,
though an export carries both. To tell whether an earlier export has gone stale,
send a POST request to ``<STUDIO_BASE>/api/courses/v0/export/versions/`` with up to
200 course ids:

.. code-block::

    {
       "courses": ["course-v1:edX+DemoX+Demo_Course", "course-v1:edX+Gone+Run"]
    }

The response reports each course's published version, how many files it has and
which was uploaded last, and how many VAL transcripts its videos have and when
any last changed. Ids that name no course on the instance are listed under
``missing`` instead of failing the request. Every value is read from an index or
an aggregate, never by walking the course, so it is cheap enough to poll for
every course on an instance.

.. code-block::

    {
        "versions": {
            "course-v1:edX+DemoX+Demo_Course": {
                "published_version": "<ObjectId of the published branch>",
                "static_assets": {
                    "count": 12,
                    "latest_upload": "2026-09-01T14:03:22+00:00",
                    "latest_asset": "asset-v1:edX+DemoX+Demo_Course+type@asset+block@syllabus.pdf"
                },
                "transcripts": {
                    "count": 40,
                    "latest_modified": "2026-09-12T09:30:00.123456+00:00"
                }
            }
        },
        "missing": ["course-v1:edX+Gone+Run"]
    }

Like the export API, it requires JWT authentication as a staff user.
