"""
Canvas Integration API endpoint urls.
"""

from django.urls import re_path

from ol_openedx_canvas_integration import views

urlpatterns = [
    re_path(
        r"^add_canvas_enrollments$",
        views.add_canvas_enrollments,
        name="add_canvas_enrollments",
    ),
    re_path(
        r"^list_canvas_enrollments$",
        views.list_canvas_enrollments,
        name="list_canvas_enrollments",
    ),
    re_path(
        r"^list_canvas_assignments$",
        views.list_canvas_assignments,
        name="list_canvas_assignments",
    ),
    re_path(
        r"^list_canvas_grades$", views.list_canvas_grades, name="list_canvas_grades"
    ),
    re_path(r"^push_edx_grades$", views.push_edx_grades, name="push_edx_grades"),
]
