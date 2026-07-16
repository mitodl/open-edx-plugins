ol-openedx-feedback
###################

An Open edX plugin that adds a per-block "Send feedback" trigger to applicable
leaf blocks in the LMS via an ``XBlockAside``.  The trigger is shown only to
authenticated learners (never in Studio author/preview mode and never to
anonymous users).

When a learner clicks the trigger the aside posts an ``ol-feedback::drawer-open``
message to its parent window (the Learning MFE) using ``window.parent.postMessage``.
The message payload carries the block context needed to identify the content
being rated:

- ``courseId`` — the course key
- ``blockUsageKey`` — the block's usage key
- ``blockType`` — the XBlock category (e.g. ``problem``, ``video``)
- ``blockDisplayName`` — the block's display name

The Learning MFE receives the message and opens the feedback drawer, which
submits the learner's feedback directly to the **mit-learn** service.  This
plugin does **not** persist anything in edx-platform and exposes no REST API.

Installation
============

Install the package into the LMS/CMS Python environment:

.. code-block:: bash

    pip install ol-openedx-feedback

The plugin registers itself automatically through its entry points — the
``xblock_asides.v1`` aside plus the ``lms.djangoapp`` / ``cms.djangoapp`` app
configs — so no changes to ``INSTALLED_APPS`` are required. Restart the LMS/CMS
after installing.

Enablement
==========

Feedback is gated by the ``ol_openedx_feedback.feedback_enabled`` course waffle
flag (default off). Enable it for the desired courses (or globally) to roll out.

Configuration
=============

By default the trigger renders on every leaf block and is suppressed only on
structural containers (``course`` / ``chapter`` / ``sequential`` / ``vertical``).
To additionally exclude one or more block types (for example ``html``), override
the excluded set through ``ENV_TOKENS`` (e.g. in ``lms.yml`` / ``cms.yml``):

.. code-block:: yaml

    OL_OPENEDX_FEEDBACK_EXCLUDED_BLOCK_TYPES:
      - course
      - chapter
      - sequential
      - vertical
      - html

The plugin reads this value via its ``settings.common`` ``plugin_settings`` hook
and exposes it as the ``OL_OPENEDX_FEEDBACK_EXCLUDED_BLOCK_TYPES`` Django
setting, defaulting to the structural set above when unset.
