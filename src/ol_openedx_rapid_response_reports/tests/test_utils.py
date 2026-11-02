"""Tests for the rapid response reports utils"""

from common.djangoapps.student.tests.factories import UserFactory
from django.core.cache import cache
from ol_openedx_rapid_response_reports.constants import RAPID_RESPONSE_ASIDE_TYPE
from ol_openedx_rapid_response_reports.utils import (
    is_rapid_response_enabled_for_course,
)
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangolib.testing.utils import skip_unless_lms
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import BlockFactory, CourseFactory


@skip_unless_lms
class IsRapidResponseEnabledForCourseTests(ModuleStoreTestCase):
    """Tests for is_rapid_response_enabled_for_course"""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.user = UserFactory.create()
        self.course = CourseFactory.create()
        self.problem = BlockFactory.create(
            parent=self.course, category="problem", display_name="Problem"
        )

    def _set_enabled(self, *, enabled):
        """Set the rapid response aside's enabled field on the problem and publish"""
        with self.store.branch_setting(
            ModuleStoreEnum.Branch.draft_preferred, self.course.id
        ):
            problem = self.store.get_item(self.problem.location)
            aside = problem.runtime.get_aside_of_type(
                problem, RAPID_RESPONSE_ASIDE_TYPE
            )
            aside.enabled = enabled
            self.store.update_item(problem, self.user.id, asides=[aside])
            self.store.publish(self.problem.location, self.user.id)

    def test_disabled_by_default(self):
        assert is_rapid_response_enabled_for_course(self.course.id) is False

    def test_enabled_for_a_problem(self):
        self._set_enabled(enabled=True)
        assert is_rapid_response_enabled_for_course(self.course.id) is True

    def test_publish_invalidates_cached_result(self):
        """A publish changes the course version, so the cached result is not reused"""
        self._set_enabled(enabled=True)
        assert is_rapid_response_enabled_for_course(self.course.id) is True
        self._set_enabled(enabled=False)
        assert is_rapid_response_enabled_for_course(self.course.id) is False

    def test_unknown_course(self):
        course_key = CourseKey.from_string("course-v1:org+missing+run")
        assert is_rapid_response_enabled_for_course(course_key) is False
