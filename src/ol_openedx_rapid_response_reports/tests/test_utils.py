"""Tests for the rapid response reports utils"""

from unittest.mock import patch

from common.djangoapps.student.tests.factories import UserFactory
from django.core.cache import cache
from ol_openedx_rapid_response_reports.constants import RAPID_RESPONSE_ASIDE_TYPE
from ol_openedx_rapid_response_reports.utils import (
    is_rapid_response_enabled_for_course,
    should_show_rapid_response_tab,
)
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangolib.testing.utils import skip_unless_lms
from rapid_response_xblock.models import RapidResponseRun
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

    def test_cached_result_is_reused(self):
        """A second call for the same course version does not rescan the problems"""
        for enabled in (False, True):
            self._set_enabled(enabled=enabled)
            assert is_rapid_response_enabled_for_course(self.course.id) is enabled
            with patch.object(
                type(self.store), "get_items", side_effect=AssertionError("rescanned")
            ):
                assert is_rapid_response_enabled_for_course(self.course.id) is enabled

    def test_unknown_course(self):
        course_key = CourseKey.from_string("course-v1:org+missing+run")
        assert is_rapid_response_enabled_for_course(course_key) is False

    def test_show_tab_when_enabled(self):
        self._set_enabled(enabled=True)
        assert should_show_rapid_response_tab(self.course.id) is True

    def test_show_tab_for_past_runs(self):
        """Reports stay reachable after rapid response is switched off again"""
        RapidResponseRun.objects.create(
            problem_usage_key=self.problem.location, course_key=self.course.id
        )
        assert is_rapid_response_enabled_for_course(self.course.id) is False
        assert should_show_rapid_response_tab(self.course.id) is True

    def test_hide_tab_when_never_used(self):
        assert should_show_rapid_response_tab(self.course.id) is False
