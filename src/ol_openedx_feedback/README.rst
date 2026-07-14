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

Enablement
==========

Feedback is gated by the ``ol_openedx_feedback.feedback_enabled`` course waffle
flag (default off). Enable it for the desired courses (or globally) to roll out.
