"""Utility functions for canvas integration"""
import logging
from collections import defaultdict

from common.djangoapps.student.models import CourseEnrollment, CourseEnrollmentAllowed
from django.contrib.auth.models import User
from lms.djangoapps.courseware.access import has_access
from lms.djangoapps.courseware.courses import get_course_by_id
from lms.djangoapps.grades.context import grading_context_for_course
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory
from opaque_keys.edx.locator import CourseLocator

from ol_openedx_canvas_integration.client import (
    CanvasClient,
    create_assignment_payload,
    update_grade_payload_kv,
)

log = logging.getLogger(__name__)


def first_or_none(iterable):
    """Returns the first item in the given iterable, or None if the iterable is empty"""
    return next((x for x in iterable), None)


def course_graded_items(course):
    grading_context = grading_context_for_course(course)
    for graded_item_type, graded_items in grading_context[
        "all_graded_subsections_by_type"
    ].items():
        for graded_item_index, graded_item in enumerate(graded_items, start=1):
            yield graded_item_type, graded_item, graded_item_index


def get_enrolled_non_staff_users(course):
    """
    Returns an iterable of non-staff enrolled users for a given course
    """
    return [
        user
        for user in CourseEnrollment.objects.users_enrolled_in(course.id)
        if not has_access(user, "staff", course)
    ]


def enroll_emails_in_course(emails, course_key):
    """
    Attempts to enroll all provided emails in a course. Emails without a corresponding
    user have a CourseEnrollmentAllowed object created for the course.
    """
    results = {}
    for email in emails:
        user = User.objects.filter(email=email).first()
        result = ""
        if not user:
            _, created = CourseEnrollmentAllowed.objects.get_or_create(
                email=email, course_id=course_key
            )
            if created:
                result = "User does not exist - created course enrollment permission"
            else:
                result = "User does not exist - enrollment is already allowed"
        elif not CourseEnrollment.is_enrolled(user, course_key):
            try:
                CourseEnrollment.enroll(user, course_key)
                result = "Enrolled user in the course"
            except Exception as ex:  # pylint: disable=broad-except
                result = f"Failed to enroll - {ex}"
        else:
            result = "User already enrolled"
        results[email] = result
    return results


def get_subsection_user_grades(course):
    """
    Builds a dict of user grades grouped by block locator. Only returns grades if the assignment has been attempted
    by the given user.

    Args:
        course: The course object (of the type returned by courseware.courses.get_course_by_id)

    Returns:
        dict: Block locators for graded items (assignments, exams, etc.) mapped to a dict of users
            and their grades for those assignments.
            Example: {
                <BlockUsageLocator for graded item>: {
                    <User object for student 1>: <grades.subsection_grade.CreateSubsectionGrade object>,
                    <User object for student 2>: <grades.subsection_grade.CreateSubsectionGrade object>,
                }
            }
    """
    enrolled_students = CourseEnrollment.objects.users_enrolled_in(course.id)
    subsection_grade_dict = defaultdict(dict)
    for student, course_grade, error in CourseGradeFactory().iter(
        users=enrolled_students, course=course
    ):
        for (
            graded_item_type,
            subsection_dict,
        ) in course_grade.graded_subsections_by_format.items():
            for subsection_block_locator, subsection_grade in subsection_dict.items():
                subsection_grade_dict[subsection_block_locator].update(
                    # Only include grades if the assignment/exam/etc. has been attempted
                    {student: subsection_grade}
                    if subsection_grade.graded_total.first_attempted
                    else {}
                )
    return subsection_grade_dict


def get_subsection_block_user_grades(course):
    """
    Builds a dict of user grades grouped by the subsection XBlock representing each graded item.
    Only returns grades if the assignment has been attempted by the given user.

    Args:
        course: The course object (of the type returned by courseware.courses.get_course_by_id)

    Returns:
        dict: Block objects representing graded items (assignments, exams, etc.) mapped to a dict of users
            and their grades for those assignments.
            Example: {
                <content.block_structure.block_structure.BlockData object for graded item>: {
                    <User object for student 1>: <grades.subsection_grade.CreateSubsectionGrade object>,
                    <User object for student 2>: <grades.subsection_grade.CreateSubsectionGrade object>,
                }
            }
    """
    subsection_user_grades = get_subsection_user_grades(course)
    graded_subsection_blocks = [
        graded_item.get("subsection_block")
        for graded_item_type, graded_item, graded_item_index in course_graded_items(
            course
        )
    ]
    locator_block_dict = {
        block_locator: first_or_none(
            block
            for block in graded_subsection_blocks
            if block.location == block_locator
        )
        for block_locator in subsection_user_grades.keys()
    }
    return {
        block: subsection_user_grades[block_locator]
        for block_locator, block in locator_block_dict.items()
        if block is not None
    }


def sync_canvas_enrollments(course_key, canvas_course_id, unenroll_current):
    """
    Fetch enrollments from canvas and update

    Args:
        course_key (str): The edX course key
        canvas_course_id (int): The canvas course id
        unenroll_current (bool): If true, unenroll existing students if not staff
    """
    client = CanvasClient(canvas_course_id)
    emails_to_enroll = client.list_canvas_enrollments()
    users_to_unenroll = []

    course_key = CourseLocator.from_string(course_key)
    course = get_course_by_id(course_key)

    if unenroll_current:
        enrolled_user_dict = {
            user.email: user for user in get_enrolled_non_staff_users(course)
        }
        emails_to_enroll_set = set(emails_to_enroll)
        already_enrolled_email_set = set(enrolled_user_dict.keys())
        emails_to_enroll = emails_to_enroll_set - already_enrolled_email_set
        users_to_unenroll = [
            enrolled_user_dict[email]
            for email in (already_enrolled_email_set - emails_to_enroll)
        ]

    enrolled = enroll_emails_in_course(emails=emails_to_enroll, course_key=course_key)
    log.info("Enrolled users in course %s: %s", course_key, enrolled)

    if users_to_unenroll:
        for user_to_unenroll in users_to_unenroll:
            CourseEnrollment.unenroll(user_to_unenroll, course.id)
        log.info(
            "Unenrolled non-staff users in course %s: %s", course_key, users_to_unenroll
        )


def push_edx_grades_to_canvas(course):
    """
    Gathers all student grades for each assignment in the given course, creates equivalent assignment in Canvas
    if they don't exist already, and adds/updates the student grades for those assignments in Canvas.

    Args:
        course: The course object (of the type returned by courseware.courses.get_course_by_id)

    Returns:
        dict: A dictionary with some information about the success/failure of the updates
    """
    canvas_course_id = course.canvas_course_id
    client = CanvasClient(canvas_course_id=canvas_course_id)
    existing_assignment_dict = client.get_assignments_by_int_id()
    subsection_block_user_grades = get_subsection_block_user_grades(course)

    # Populate missing assignments
    new_assignment_blocks = (
        subsection_block
        for subsection_block in subsection_block_user_grades.keys()
        if str(subsection_block.location) not in existing_assignment_dict
    )
    created_assignments = {
        subsection_block: client.create_canvas_assignment(
            create_assignment_payload(subsection_block)
        )
        for subsection_block in new_assignment_blocks
    }

    # Build request payloads for updating grades in each assignment
    enrolled_user_dict = client.list_canvas_enrollments()
    grade_update_payloads = {}
    for subsection_block, user_grade_dict in subsection_block_user_grades.items():
        grade_update_payloads[subsection_block] = dict(
            update_grade_payload_kv(
                enrolled_user_dict[student_user.email.lower()], grade.percent_graded
            )
            for student_user, grade in user_grade_dict.items()
            # Only add the grade if the user exists in Canvas
            if student_user.email.lower() in enrolled_user_dict
        )

    # Send requests to update grades in each relevant course
    assignment_grades_updated = {
        subsection_block: client.update_assignment_grades(
            canvas_assignment_id=existing_assignment_dict[
                str(subsection_block.location)
            ],
            payload=grade_request_payload,
        )
        for subsection_block, grade_request_payload in grade_update_payloads.items()
        if grade_request_payload
        and str(subsection_block.location) in existing_assignment_dict
    }

    return assignment_grades_updated, created_assignments
