Change Log
----------

..
   All enhancements and patches to ol_openedx_chat will be documented
   in this file.  It adheres to the structure of https://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (https://semver.org/).
.. There should always be an "Unreleased" section for changes pending release.

Unreleased
~~~~~~~~~~

[0.7.0] - 2026-10-28
~~~~~~~~~~~~~~~~~~~~
Added
-----
* ``ol_openedx_chat.contact_us_enabled`` course waffle flag, and a
  ``/ol-openedx-chat/api/contact-us-enabled/[{course_key}]`` endpoint that reports
  it, so the Contact us launcher in the MFEs can be turned off site-wide or
  per course without a frontend build.
