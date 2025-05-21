"""
Tests for models
"""

import pytest
from django.core.exceptions import ValidationError
from ol_openedx_course_sync.models import CourseRunSyncMap
from openedx.core.djangolib.testing.utils import skip_unless_cms


@skip_unless_cms
@pytest.mark.django_db()
@pytest.mark.parametrize(
    ("existing", "new", "expected_error_field"),
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
            "target_course",
        ),
    ],
)
def test_course_run_sync_map_clean_conflicts(existing, new, expected_error_field):
    """
    Parametrized test to validate CourseRunSyncMap.clean() conflicts:
    - A source course cannot be used as a target.
    - A target course cannot be used as a source.
    """
    CourseRunSyncMap.objects.create(**existing)
    obj = CourseRunSyncMap(**new)

    with pytest.raises(ValidationError) as context:
        obj.full_clean()
    assert expected_error_field in context.value.error_dict


@skip_unless_cms
def test_valid_course_run_sync_map():
    """Valid CourseRunSyncMap instance should pass validation."""
    obj = CourseRunSyncMap(
        source_course="course-v1:edX+DemoX+2040",
        target_course="course-v1:edX+DemoX+2041",
    )
    obj.full_clean()  # Should not raise
