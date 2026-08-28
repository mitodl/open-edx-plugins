LTI Utilities Plugin
=============================

A django app plugin to add LTI related utilities in Open edX platform.


Version Compatibility
----------------------

See the `Open edX Release Compatibility table <../../docs#open-edx-release-compatibility>`_
in the repository docs for the minimum plugin version required per Open edX
release (Django 5.2 floor on Ulmo/Verawood and later).

Installation
------------

For detailed installation instructions, please refer to the `plugin installation guide <../../docs#installation-guide>`_.

Installation required in:

* LMS

How To Use
----------

**API Request**

To manually call the API, Send a POST request to ``<LMS_BASE>/lti-user-fix/`` with a JSON body containing the following field:
 - ``email``: The email address of the user whose LTI account needs to be fixed.

A sample request looks like below:

::

    POST: http://local.openedx.io:8000/api/lti-user-fix/

    Payload:
    {
        "email": "user@example.com"
    }


API Response
------------

The successful response would be an indication that an LTI user in bad state was found and fixed. The response status code would be 200.
