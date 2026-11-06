Change Log
##########

..
   All enhancements and patches to ol_openedx_course_outline_api will be documented
   in this file.  It adheres to the structure of https://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (https://semver.org/).

.. There should always be an "Unreleased" section for changes pending release.

Unreleased
**********

*

[0.2.2] - 2026-11-06
********************

Fixed
=====

* Cache the course outline under the collected block structure's version
  instead of the modulestore's ``course_version``. An outline rendered before
  the block structure finished rebuilding was previously filed under the
  post-publish key and served for the full cache lifetime, so sections hidden
  in Studio kept appearing. The version covers every field the platform
  compares in ``BlockStructureStore.is_up_to_date``, so a recollection that
  leaves ``course_version`` untouched still produces a new key. Bumps the
  cache schema version, which abandons existing entries.
* Skip caching entirely when no collected block structure exists yet. That
  request builds the structure as a side effect, so no version yet names the
  content being returned; the next request caches normally.

Added
=====

* First test suite for this plugin, including a regression test that reproduces
  the reported bug: a section hidden in Studio stayed in the outline because the
  response rendered during the structure rebuild was pinned for the full TTL.
