"""
Canvas Integration API endpoint urls.
"""

from django.urls import path

from ol_openedx_canvas_integration import views

urlpatterns = [
    path(
        "add_canvas_enrollments",
        views.add_canvas_enrollments,
        name="add_canvas_enrollments",
    ),
    path(
        "list_canvas_enrollments",
        views.list_canvas_enrollments,
        name="list_canvas_enrollments",
    ),
    path(
        "list_canvas_assignments",
        views.list_canvas_assignments,
        name="list_canvas_assignments",
    ),
    path("list_canvas_grades", views.list_canvas_grades, name="list_canvas_grades"),
    path("push_edx_grades", views.push_edx_grades, name="push_edx_grades"),
]
