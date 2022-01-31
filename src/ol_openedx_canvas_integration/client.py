import logging
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import pytz
import requests
from django.conf import settings

from ol_openedx_canvas_integration.constants import DEFAULT_ASSIGNMENT_POINTS

log = logging.getLogger(__name__)


class CanvasClient:
    def __init__(self, canvas_course_id):
        self.session = self.get_canvas_session()
        self.canvas_course_id = canvas_course_id

    @staticmethod
    def get_canvas_session():
        """
        Create a request session with the access token
        """
        session = requests.Session()
        session.headers.update(
            {"Authorization": f"Bearer {settings.CANVAS_ACCESS_TOKEN}"}
        )
        return session

    @staticmethod
    def _add_per_page(url, per_page):
        """
        Add per_page query parameter to override default value of 10

        Args:
            url (str): The url to update
            per_page (int): The new per_page value

        Returns:
            str: The updated URL
        """
        pieces = urlparse(url)
        query = parse_qs(pieces.query)
        query["per_page"] = per_page
        query_string = urlencode(query, doseq=True)
        pieces = pieces._replace(query=query_string)
        return pieces.geturl()

    def _paginate(self, url, *args, **kwargs):
        """
        Iterate over the paginated results of a request
        """
        url = self._add_per_page(
            url, 100
        )  # increase per_page to 100 from default of 10

        items = []
        while url:
            resp = self.session.get(url, *args, **kwargs)
            resp.raise_for_status()
            items.extend(resp.json())
            links = requests.utils.parse_header_links(resp.headers["link"])
            url = None
            for link in links:
                if link["rel"] == "next":
                    url = link["url"]

        return items

    def list_canvas_enrollments(self):
        """
        Fetch canvas enrollments. This may take a while, so don't run in the request thread.

        Returns:
            dict: Email addresses mapped to canvas user ids for all enrolled users
        """
        url = urljoin(
            settings.CANVAS_BASE_URL,
            f"/api/v1/courses/{self.canvas_course_id}/enrollments",
        )
        enrollments = self._paginate(url)

        return {
            enrollment["user"]["login_id"].lower(): enrollment["user"]["id"]
            for enrollment in enrollments
        }

    def list_canvas_assignments(self):
        """
        List Canvas assignments

        Returns:
            list: A list of assignment dicts from Canvas
        """
        url = urljoin(
            settings.CANVAS_BASE_URL,
            "/api/v1/courses/{course_id}/assignments".format(
                course_id=self.canvas_course_id
            ),
        )
        return self._paginate(url)

    def get_assignments_by_int_id(self):
        assignments = self.list_canvas_assignments()
        assignments_dict = {
            assignment.get("integration_id"): assignment["id"]
            for assignment in assignments
            if assignment.get("integration_id") is not None
        }
        assignments_without_integration_id = sorted(
            assignment["id"]
            for assignment in assignments
            if assignment.get("integration_id") is None
        )
        if assignments_without_integration_id:
            log.warning(
                "These assignments are missing an integration_id: %s",
                ", ".join(
                    str(assignment_id)
                    for assignment_id in assignments_without_integration_id
                ),
            )
        return assignments_dict

    def list_canvas_grades(self, assignment_id):
        """
        List grades for a Canvas assignment

        Args:
            assignment_id (int): The canvas assignment id
        """
        url = urljoin(
            settings.CANVAS_BASE_URL,
            "/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions".format(
                course_id=self.canvas_course_id,
                assignment_id=assignment_id,
            ),
        )
        return self._paginate(url)

    def create_canvas_assignment(self, payload):
        """
        Create an assignment on Canvas

        Args:
            payload (dict):
        """
        return self.session.post(
            url=urljoin(
                settings.CANVAS_BASE_URL,
                f"/api/v1/courses/{self.canvas_course_id}/assignments",
            ),
            json=payload,
        )

    def update_assignment_grades(self, canvas_assignment_id, payload):
        return self.session.post(
            url=urljoin(
                settings.CANVAS_BASE_URL,
                "/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/update_grades".format(
                    course_id=self.canvas_course_id, assignment_id=canvas_assignment_id
                ),
            ),
            data=payload,
        )


def create_assignment_payload(subsection_block):
    """
    Create a Canvas assignment dict matching a subsection block on edX

    Args:
        subsection_block (openedx.core.djangoapps.content.block_structure.block_structure.BlockData):
            The block data for the graded assignment/exam (in the structure of a course, this unit is a subsection)

    Returns:
        dict:
            Assignment payload to be sent to Canvas to create or update the assignment
    """
    return {
        "assignment": {
            "name": subsection_block.display_name,
            "integration_id": str(subsection_block.location),
            "grading_type": "percent",
            "points_possible": DEFAULT_ASSIGNMENT_POINTS,
            "due_at": (
                None
                if not subsection_block.fields.get("due")
                # The internal API gives us a TZ-naive datetime for the due date, but Studio indicates that
                # the user should enter a UTC datetime for the due date. Coerce this to UTC before creating the
                # string representation.
                else subsection_block.fields["due"].astimezone(pytz.UTC).isoformat()
            ),
            "submission_types": ["none"],
            "published": False,
        }
    }


def update_grade_payload_kv(user_id, grade_percent):
    """
    Returns a key/value pair that will be used in the body of a bulk grade update request

    Args:
        user_id (int): The Canvas user ID
        grade_percent (numpy.float64): The percent score of the grade (between 0 and 1)

    Returns:
        (tuple): A key/value pair that will be used in the body of a bulk grade update request
    """
    return (f"grade_data[{user_id}][posted_grade]", f"{grade_percent * 100}%")
