"""URLs for ol_openedx_feedback."""

from django.urls import path

from ol_openedx_feedback.views import FeedbackSubmissionView

urlpatterns = [
    path(
        "submissions/",
        FeedbackSubmissionView.as_view(),
        name="feedback_submissions",
    ),
]
