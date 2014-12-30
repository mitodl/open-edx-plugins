import json

from django.core.management.base import BaseCommand, CommandError

from courseware.courses import get_course_by_id
from courseware.models import StudentModule
from opaque_keys.edx.keys import CourseKey
from student.models import anonymous_id_for_user
from submissions import api as submissions_api


class Command(BaseCommand):
    """
    Migrates existing SGA submissions for a course from old SGA implementation
    to newer version that uses the 'submissions' application.
    """
    args = "<course_id>"
    help = __doc__

    def handle(self, *args, **options):
        if not args:
            raise CommandError('Please specify the course id.')
        if len(args) > 1:
            raise CommandError('Too many arguments.')
        course_id = args[0]
        course_key = CourseKey.from_string(course_id)
        course = get_course_by_id(course_key)

        student_modules = StudentModule.objects.filter(course_id=course.id)
        for student_module in student_modules:
            block_id = student_module.module_state_key
            if block_id.block_type != 'edx_sga':
                continue
            state = json.loads(student_module.state)
            sha1 = state.get('uploaded_sha1')
            if not sha1:
                continue
            student = student_module.student
            submission_id = {
                'student_id': anonymous_id_for_user(student, course.id),
                'course_id': course.id,
                'item_id': block_id,
                'item_type': 'sga',
            }
            answer = {
                "sha1": sha1,
                "filename": state.get('uploaded_filename'),
                "mimetype": state.get('uploaded_mimetype'),
            }
            submissions_api.create_submission(submission_id, answer)
