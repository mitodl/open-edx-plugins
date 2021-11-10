
from django.urls import reverse
from django.utils.translation import ugettext as _


def plugin_context(context):
    course = context["course"]
    """ Provide data for the canvas dashboard section """
    return {
        'section_key': 'canvas_integration',
        'section_display_name': _('Canvas'),
        'course': course,
        'add_canvas_enrollments_url': reverse(
            'add_canvas_enrollments', kwargs={'course_id': course.id}
        ),
        "list_canvas_enrollments_url": reverse("list_canvas_enrollments", kwargs={"course_id": course.id}),
        "list_canvas_assignments_url": reverse("list_canvas_assignments", kwargs={"course_id": course.id}),
        "list_canvas_grades_url": reverse("list_canvas_grades", kwargs={"course_id": course.id}),
        'list_instructor_tasks_url': '{}?include_canvas=true'.format(reverse(
            'list_instructor_tasks',
            kwargs={'course_id': course.id}
        )),
        "push_edx_grades_url": reverse(
            "push_edx_grades", kwargs={"course_id": course.id}
        ),
    }
