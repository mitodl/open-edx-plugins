"""Utilities for Canvas plugin"""


def get_canvas_course_id(course=None):
    """Get the course Id from the course settings"""
    return course.other_course_settings.get("canvas_id") if course else None


def get_task_output_formatted_message(task_output):
    """Take the edX task output and format a message for table display on task result"""
    # this reports on actions for a course as a whole
    results = task_output.get("results", {})
    assignments_count = results.get("assignments", 0)
    grades_count = results.get("grades", 0)

    return (
        f"{grades_count} grades and {assignments_count} assignments updated or created"
    )
