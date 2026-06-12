ol-openedx-feedback
###################

An Open edX plugin that lets authenticated learners submit a 1-5 rating and an
optional comment about any course block. A small trigger is rendered on each
applicable block via an ``XBlockAside``; clicking it opens a feedback drawer in
the Learning MFE. Submissions are persisted in edx-platform via a REST API and a
tracking event is emitted so the data reaches the data platform. A staff/service
read endpoint exposes the collected feedback to other services.

Enablement
==========

Feedback is gated by the ``ol_openedx_feedback.feedback_enabled`` course waffle
flag (default off). Enable it for the desired courses (or globally) to roll out.

API
===

- ``POST /api/feedback/v1/submissions/`` — authenticated learners submit feedback.
- ``GET  /api/feedback/v1/submissions/`` — staff/services read feedback
  (supports ``course_id``, ``block_usage_key`` and ``since`` query params).
