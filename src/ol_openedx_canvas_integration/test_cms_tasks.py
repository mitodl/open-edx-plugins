import pytest

from uuid import uuid4
from ol_openedx_canvas_integration.cms_tasks import diff_assignments
from ol_openedx_canvas_integration.api import create_assignment_payload


class MockSubsection:
    def __init__(self, location) -> None:
        self.location = location
        self.display_name = "Mock Assignment in " + str(location)
        self.fields = {}

    @property
    def payload(self):
        return create_assignment_payload(self)


subsection_mocks = [MockSubsection(f'id-{i}') for i in range(10)]


@pytest.mark.parametrize(
    "openedx_assignments,canvas_assignments_map,expected_output",
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
                "delete": []
            }
        ),
        # Update existing assignments
        (
            subsection_mocks[8:],
            {
                "id-8": 1008,
                "id-9": 1009,
            },
            {
                "add": [],
                "update": {
                    1008: subsection_mocks[8].payload,
                    1009: subsection_mocks[9].payload,
                },
                "delete": [],
            }
        ),
        # Remove existing assignments
        (
            [],
            {
                "synced-1": 1002,
                "synced-2": 1003,
            },
            {
                "add": [],
                "update": {},
                "delete": [1002, 1003]
            }
        ),
        # Add some, update some and remove some assignments
        (
            subsection_mocks[4:8],
            {
                "id-2": 12, # remove
                "id-3": 13, # remove
                "id-4": 14, # update
                "id-5": 15, # update
            },
            {
                "add": [s.payload for s in subsection_mocks[6:8]],
                "update": {
                    14: subsection_mocks[4].payload,
                    15: subsection_mocks[5].payload,
                },
                "delete": [12, 13],
            }
        )
    ]
)
def test_diff_assignments(openedx_assignments, canvas_assignments_map, expected_output):
    assert diff_assignments(openedx_assignments, canvas_assignments_map) == expected_output
