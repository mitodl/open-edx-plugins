"""
Canvas Integration API endpoint urls.
"""

from django.conf.urls import url

from ol_openedx_canvas_integration import views

urlpatterns = [
    url(
        r"^add_canvas_enrollments$",
        views.add_canvas_enrollments,
        name="add_canvas_enrollments",
    ),
    url(
        r"^list_canvas_enrollments$",
        views.list_canvas_enrollments,
        name="list_canvas_enrollments",
    ),
    url(
        r"^list_canvas_assignments$",
        views.list_canvas_assignments,
        name="list_canvas_assignments",
    ),
    url(r"^list_canvas_grades$", views.list_canvas_grades, name="list_canvas_grades"),
    url(r"^push_edx_grades$", views.push_edx_grades, name="push_edx_grades"),
]
