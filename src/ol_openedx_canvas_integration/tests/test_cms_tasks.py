from __future__ import annotations

import pytest
from ol_openedx_canvas_integration.api import create_assignment_payload
from ol_openedx_canvas_integration.cms_tasks import diff_assignments


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
