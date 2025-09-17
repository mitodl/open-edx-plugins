"""
Tests for models
"""

import pytest
from django.core.exceptions import ValidationError
from ol_openedx_course_sync.models import CourseSyncMapping
from opaque_keys.edx.locator import CourseLocator
from openedx.core.djangoapps.content.course_overviews.tests.factories import (
    CourseOverviewFactory,
)
from openedx.core.djangolib.testing.utils import skip_unless_cms


@skip_unless_cms
@pytest.mark.django_db
@pytest.mark.parametrize(
    ("existing", "new", "course_overview_exists", "expected_error_field"),
    [
        # Case 1: source_course is already a target_course elsewhere
        (
            {
                "source_course": "course-v1:edX+DemoX+2025",
                "target_course": "course-v1:edX+DemoX+2026",
            },
            {
                "source_course": "course-v1:edX+DemoX+2026",
                "target_course": "course-v1:edX+DemoX+2027",
            },
            True,
            "source_course",
        ),
        # Case 2: target_course is already a source_course elsewhere
        (
            {
                "source_course": "course-v1:edX+DemoX+2028",
                "target_course": "course-v1:edX+DemoX+2029",
            },
            {
                "source_course": "course-v1:edX+DemoX+2030",
                "target_course": "course-v1:edX+DemoX+2028",
            },
            True,
            "target_course",
        ),
        # Case 3: target_course is already used as target_course in another mapping
        (
            {
                "source_course": "course-v1:edX+DemoX+2031",
                "target_course": "course-v1:edX+DemoX+2032",
            },
            {
                "source_course": "course-v1:edX+DemoX+2033",
                "target_course": "course-v1:edX+DemoX+2032",
            },
            True,
            "target_course",
        ),
        # Case 4: Success, target and source courses are not in conflict
        (
            {
                "source_course": "course-v1:edX+DemoX+2025",
                "target_course": "course-v1:edX+DemoX+2026",
            },
            {
                "source_course": "course-v1:edX+DemoX+2025",
                "target_course": "course-v1:edX+DemoX+2027",
            },
            True,
            None,
        ),
        # Case 5: Failure, target course overview does not exist
        (
            {
                "source_course": "course-v1:edX+DemoX+2025",
                "target_course": "course-v1:edX+DemoX+2026",
            },
            {
                "source_course": "course-v1:edX+DemoX+2025",
                "target_course": "course-v1:edX+DemoX+2027",
            },
            False,
            "target_course",
        ),
    ],
)
def test_course_sync_mapping_clean(
    existing, new, course_overview_exists, expected_error_field
):
    """
    Parametrized test to validate CourseSyncMapping.clean() conflicts:
    - A source course cannot be used as a target.
    - A target course cannot be used as a source.
    - Course overview should exist.
    """
    CourseOverviewFactory.create(
        id=CourseLocator.from_string(existing["source_course"])
    )
    CourseOverviewFactory.create(
        id=CourseLocator.from_string(existing["target_course"])
    )

    if course_overview_exists:
        CourseOverviewFactory.create(id=CourseLocator.from_string(new["source_course"]))
        CourseOverviewFactory.create(id=CourseLocator.from_string(new["target_course"]))

    CourseSyncMapping.objects.create(**existing)
    obj = CourseSyncMapping(**new)

    if expected_error_field:
        with pytest.raises(ValidationError) as context:
            obj.full_clean()
        assert expected_error_field in context.value.error_dict
    else:
        obj.save()
