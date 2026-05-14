from __future__ import annotations

from unittest.mock import ANY, MagicMock, call, patch

import ddt
import pytest
from common.djangoapps.student.tests.factories import UserFactory
from django.contrib.auth.models import User
from django.test import override_settings
from django.utils.dateparse import parse_datetime
from ol_openedx_canvas_integration.api import create_assignment_payload
from ol_openedx_canvas_integration.cms_tasks import (
    _sync_canvas_due_dates,
    diff_assignments,
    sync_canvas_due_dates_for_all_courses,
)
from opaque_keys.edx.keys import UsageKey
from openedx.core.djangoapps.content.course_overviews.tests.factories import (
    CourseOverviewFactory,
)
from openedx.core.djangolib.testing.utils import skip_unless_cms
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import BlockFactory, CourseFactory


class MockSubsection:
    """Subsection stub that exposes a precomputed Canvas payload helper."""

    def __init__(self, location) -> None:
        """Initialize subsection identity and display metadata."""
        self.location = location
        self.display_name = "Mock Assignment in " + str(location)
        self.fields: dict[str, str] = {}

    @property
    def payload(self):
        """Return the Canvas assignment payload for this subsection."""
        return create_assignment_payload(self)


subsection_mocks = [MockSubsection(f"id-{i}") for i in range(10)]


def make_assignment(assignment_id: int, due_at: str | None = None):
    return {
        "id": assignment_id,
        "due_at": due_at,
    }


@skip_unless_cms
@pytest.mark.parametrize(
    ("openedx_assignments", "canvas_assignments_map", "expected_output"),
    [
        # All empty
        ([], {}, {"add": [], "update": {}, "delete": []}),
        # Add new assignments to Canvas
        (
            subsection_mocks[0:3],
            {},
            {
                "add": [s.payload for s in subsection_mocks[0:3]],
                "update": {},
                "delete": [],
            },
        ),
        # Update existing assignments
        (
            subsection_mocks[8:],
            {
                "id-8": {"id": 1008},
                "id-9": {"id": 1009},
            },
            {
                "add": [],
                "update": {
                    1008: subsection_mocks[8].payload,
                    1009: subsection_mocks[9].payload,
                },
                "delete": [],
            },
        ),
        # Remove existing assignments
        (
            [],
            {
                "synced-1": {"id": 1002},
                "synced-2": {"id": 1003},
            },
            {"add": [], "update": {}, "delete": [1002, 1003]},
        ),
        # Add some, update some and remove some assignments
        (
            subsection_mocks[4:8],
            {
                "id-2": {"id": 12},  # remove
                "id-3": {"id": 13},  # remove
                "id-4": {"id": 14},  # update
                "id-5": {"id": 15},  # update
            },
            {
                "add": [s.payload for s in subsection_mocks[6:8]],
                "update": {
                    14: subsection_mocks[4].payload,
                    15: subsection_mocks[5].payload,
                },
                "delete": [12, 13],
            },
        ),
    ],
)

def test_diff_assignments(openedx_assignments, canvas_assignments_map, expected_output):
    """Test that diff assignments."""
    assert (
        diff_assignments(openedx_assignments, canvas_assignments_map) == expected_output
    )

@skip_unless_cms
@override_settings(BULK_EMAIL_DEFAULT_RETRY_DELAY=10, BULK_EMAIL_MAX_RETRIES=5)
@ddt.ddt
class CanvasDueDateSyncTests(ModuleStoreTestCase):
    def setUp(self):
        super().setUp()

    def create_course(self, other_course_settings: dict | None = None):
        if other_course_settings is None:
            other_course_settings = {}
        course = CourseFactory.create(other_course_settings=other_course_settings)
        chapter = BlockFactory.create(
            parent=course,
            category="chapter",
            display_name="Chapter",
        )
        sequential1 = BlockFactory.create(
            parent=chapter,
            category="sequential",
            display_name="Lesson 1",
        )
        BlockFactory.create(
            parent=sequential1,
            category="vertical",
            display_name="Subsection 1",
        )
        sequential2 = BlockFactory.create(
            parent=chapter,
            category="sequential",
            display_name="Lesson 2",
        )
        BlockFactory.create(
            parent=sequential2,
            category="vertical",
            display_name="Subsection 2",
        )
        return course, [sequential1, sequential2]

    @ddt.data(
        {"canvas_id": ""},
        {"canvas_id": None},
        {},
    )
    def test_sync_canvas_due_dates_no_canvas_id(self, other_course_settings):
        course, _ = self.create_course(other_course_settings)
        canvas_client_mock = MagicMock()

        with (
            patch(
                "ol_openedx_canvas_integration.cms_tasks.CanvasClient",
                return_value=canvas_client_mock,
            ),
        ):
            _sync_canvas_due_dates(str(course.id))

            canvas_client_mock.get_canvas_assignments.assert_not_called()

    @ddt.data(
        {},
        {"use_canvas_due_dates": False},
    )
    def test_sync_canvas_due_dates_due_dates_disabled(self, other_course_settings):
        course, _ = self.create_course(
            {
                "canvas_id": 11,
                **other_course_settings,
            }
        )
        canvas_client_mock = MagicMock()

        with (
            patch(
                "ol_openedx_canvas_integration.cms_tasks.CanvasClient",
                return_value=canvas_client_mock,
            ),
        ):
            _sync_canvas_due_dates(str(course.id))

            canvas_client_mock.get_canvas_assignments.assert_not_called()

    def test_sync_canvas_due_dates_updates_due_dates(self):
        course, sequentials = self.create_course(
            {
                "canvas_id": 11,
                "use_canvas_due_dates": True,
            }
        )

        mock_canvas_assignments = {
            str(sequentials[0].location): {"due_at": "2026-06-01T00:00:00Z"},
            str(sequentials[1].location): {"due_at": None},
        }

        canvas_client_mock = MagicMock()
        canvas_client_mock.get_canvas_assignments.return_value = mock_canvas_assignments

        with (
            patch(
                "ol_openedx_canvas_integration.cms_tasks.CanvasClient",
                return_value=canvas_client_mock,
            ),
        ):
            _sync_canvas_due_dates(str(course.id))

            for seq_id, data in mock_canvas_assignments.items():
                seq_key = UsageKey.from_string(seq_id)
                due_at = data.get("due_at", None)
                due_at = parse_datetime(due_at) if due_at else None
                assert self.store.get_item(seq_key).due == due_at

    def test_sync_canvas_due_date_extensions(self):
        for uid in [1, 4, 9, 11, 14, 37]:
            UserFactory.create(username=f"user{uid}", email=f"user{uid}@abc.xyz")
        course, sequentials = self.create_course(
            {
                "canvas_id": 11,
                "use_canvas_due_dates": True,
            }
        )

        sequential_0_student_ids = [11, 37, 4]
        sequential_1_student_ids = [1, 9, 14]

        mock_canvas_assignments = {
            str(sequentials[0].location): {
                "due_at": "2026-06-01T00:00:00Z",
                "overrides": [
                    {
                        "due_at": "2026-06-02T00:00:00Z",
                        "student_ids": sequential_0_student_ids,
                    }
                ],
            },
            str(sequentials[1].location): {
                "due_at": None,
                "overrides": [
                    {
                        "due_at": "2026-06-04T00:00:00Z",
                        "student_ids": sequential_1_student_ids,
                    }
                ],
            },
        }

        canvas_client_mock = MagicMock()
        canvas_client_mock.get_canvas_assignments.return_value = mock_canvas_assignments
        canvas_client_mock.get_emails_by_student_ids.side_effect = lambda ids: [
            f"user{uid}@abc.xyz" for uid in ids
        ]

        with (
            patch(
                "ol_openedx_canvas_integration.cms_tasks.CanvasClient",
                return_value=canvas_client_mock,
            ),
            patch(
                "ol_openedx_canvas_integration.cms_tasks.set_due_date_extension"
            ) as set_due_date_extension_mock,
        ):
            _sync_canvas_due_dates(str(course.id))
            # 3 student extensions each for 2 assignments
            assert set_due_date_extension_mock.call_count == (
                len(sequential_0_student_ids) + len(sequential_1_student_ids)
            )
            for call_args, _ in set_due_date_extension_mock.call_args_list:
                assert call_args[0].id == course.id
                assert call_args[1].location in (
                    sequentials[0].location,
                    sequentials[1].location,
                )

            for student_id in sequential_0_student_ids:
                for _ in sequentials:
                    set_due_date_extension_mock.assert_any_call(
                        ANY,
                        ANY,
                        User.objects.get(email=f"user{student_id}@abc.xyz"),
                        parse_datetime("2026-06-02T00:00:00Z"),
                        reason="Synced from canvas course: 11",
                    )

    def test_sync_canvas_due_date_extensions_with_only_until_date(self):
        """
        A Canvas override that sets only an "Until" date (lock_at) and no "Due"
        date has `due_at: None`. Syncing such an override must not raise.
        """
        for uid in [1, 4]:
            UserFactory.create(username=f"user{uid}", email=f"user{uid}@abc.xyz")
        course, sequentials = self.create_course(
            {
                "canvas_id": 11,
                "use_canvas_due_dates": True,
            }
        )

        student_ids = [1, 4]

        mock_canvas_assignments = {
            str(sequentials[0].location): {
                "due_at": None,
                "overrides": [
                    {
                        "due_at": None,
                        "lock_at": "2026-06-02T00:00:00Z",
                        "student_ids": student_ids,
                    }
                ],
            },
        }

        canvas_client_mock = MagicMock()
        canvas_client_mock.get_canvas_assignments.return_value = mock_canvas_assignments
        canvas_client_mock.get_emails_by_student_ids.side_effect = lambda ids: [
            f"user{uid}@abc.xyz" for uid in ids
        ]

        with (
            patch(
                "ol_openedx_canvas_integration.cms_tasks.CanvasClient",
                return_value=canvas_client_mock,
            ),
            patch(
                "ol_openedx_canvas_integration.cms_tasks.set_due_date_extension"
            ) as set_due_date_extension_mock,
        ):
            _sync_canvas_due_dates(str(course.id))

        set_due_date_extension_mock.assert_not_called()

    def test_sync_canvas_due_dates_for_all_courses_enqueues_each_course(self):
        course_1, _ = self.create_course()
        course_2, _ = self.create_course()
        course_3, _ = self.create_course()

        CourseOverviewFactory.create(id=course_1.id)
        CourseOverviewFactory.create(id=course_2.id)
        CourseOverviewFactory.create(id=course_3.id)

        with patch(
            "ol_openedx_canvas_integration.cms_tasks.sync_canvas_due_dates.delay"
        ) as sync_canvas_due_dates_delay_mock:
            sync_canvas_due_dates_for_all_courses()

        sync_canvas_due_dates_delay_mock.assert_has_calls(
            [
                call(str(course_1.id)),
                call(str(course_2.id)),
                call(str(course_3.id)),
            ]
        )
        assert sync_canvas_due_dates_delay_mock.call_count == 3  # noqa: PLR2004

    def test_sync_canvas_due_dates_for_all_courses_with_no_courses(self):
        with patch(
            "ol_openedx_canvas_integration.cms_tasks.sync_canvas_due_dates.delay"
        ) as sync_canvas_due_dates_delay_mock:
            sync_canvas_due_dates_for_all_courses()

        sync_canvas_due_dates_delay_mock.assert_not_called()
