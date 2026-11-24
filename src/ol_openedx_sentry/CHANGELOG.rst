Change Log
##########

..
   All enhancements and patches to ol_openedx_sentry will be documented
   in this file.  It adheres to the structure of https://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (https://semver.org/).

.. There should always be an "Unreleased" section for changes pending release.

Unreleased
**********

*

[0.6.2] - 2026-11-24
********************

Fixed
=====

* Cap ``sentry-sdk`` below 3. sentry-sdk 3.0.0 removed the ``send_default_pii``
  option, so ``sentry_sdk.init`` raised ``TypeError: Unknown option
  'send_default_pii'`` at settings load.
