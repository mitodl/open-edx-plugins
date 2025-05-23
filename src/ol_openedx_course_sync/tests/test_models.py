"""
Tests for models
"""

import pytest
from django.core.exceptions import ValidationError
from ol_openedx_course_sync.models import CourseSyncMapping
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
                None,
        ),
    ],
)
def test_course_sync_mapping_clean_conflicts(existing, new, expected_error_field):
    """
    Parametrized test to validate CourseSyncMapping.clean() conflicts:
    - A source course cannot be used as a target.
    - A target course cannot be used as a source.
    """
    CourseSyncMapping.objects.create(**existing)
    obj = CourseSyncMapping(**new)

    if expected_error_field:
        with pytest.raises(ValidationError) as context:
            obj.full_clean()
        assert expected_error_field in context.value.error_dict
    else:
        obj.save()
