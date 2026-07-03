Change Log
----------

..
   All enhancements and patches to ol_openedx_chat_xblock will be documented
   in this file.  It adheres to the structure of https://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (https://semver.org/).
.. There should always be an "Unreleased" section for changes pending release.

Unreleased
~~~~~~~~~~

[0.4.6] - 2026-07-03
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Fixed
-----
* Register the chat xBlock render filter in production settings so it survives the
  deployment's wholesale ``OPEN_EDX_FILTERS_CONFIG`` override in
  ``lms/envs/production.py`` (previously registered only in common settings, so it
  relied on the deployment wiring the filter up).
