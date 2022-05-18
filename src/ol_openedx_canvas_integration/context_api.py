"""
The initialization of the context for the Canvas Integration Plugin
"""
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse
from django.utils.translation import ugettext as _
from web_fragments.fragment import Fragment


def plugin_context(context):
    """Provide context based data for Canvas Integration plugin (For Instructor Dashboard)"""
    fragment = Fragment()
    course = context.get("course")

    fragment.add_javascript_url(staticfiles_storage.url("/js/canvas_integration.js"))

    canvas_context = {
        "section_key": "canvas_integration",
        "section_display_name": _("Canvas"),
        "course": context["course"],
        "add_canvas_enrollments_url": reverse(
            "add_canvas_enrollments", kwargs={"course_id": course.id}
        ),
        "list_canvas_enrollments_url": reverse(
            "list_canvas_enrollments", kwargs={"course_id": course.id}
        ),
        "list_canvas_assignments_url": reverse(
            "list_canvas_assignments", kwargs={"course_id": course.id}
        ),
        "list_canvas_grades_url": reverse(
            "list_canvas_grades", kwargs={"course_id": course.id}
        ),
        "list_instructor_tasks_url": "{}?include_canvas=true".format(
            reverse("list_instructor_tasks", kwargs={"course_id": course.id})
        ),
        "push_edx_grades_url": reverse(
            "push_edx_grades", kwargs={"course_id": course.id}
        ),
        "fragment": fragment,
        "template_path_prefix": "/",
    }

    sections = context.get("sections", [])
    sections.append(canvas_context)
    context["sections"] = sections

    return context
