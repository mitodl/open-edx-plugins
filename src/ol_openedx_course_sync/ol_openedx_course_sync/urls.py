"""URLs for the ol-openedx-course-sync plugin"""

from django.urls import path

from ol_openedx_course_sync import views

urlpatterns = [
    path(
        "sync_problem_actions",
        views.sync_problem_actions,
        name="sync_problem_actions",
    ),
]
