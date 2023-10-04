"""Views for Course structure API"""

import logging

# dump_block is renamed from dump_module in release-2023-03-08-14.35
# For backward compatibility, try import the new name and then old name
try:
    from lms.djangoapps.courseware.management.commands.dump_course_structure import (
        dump_block,
    )
except ImportError:
    try:
        from lms.djangoapps.courseware.management.commands.dump_course_structure import (  # noqa: E501
            dump_module as dump_block,
        )
    except ImportError as exc:
        msg = "Couldn't import dump_block or dump_module"
        raise ImportError(msg) from exc

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from openedx.core.lib.api.view_utils import (
    DeveloperErrorViewMixin,
    verify_course_exists,
)
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.inheritance import compute_inherited_metadata

log = logging.getLogger(__name__)


class CourseStructureView(DeveloperErrorViewMixin, GenericAPIView):
    """
    An API View for course structure

    **Example Requests**

    GET api/course-structure/v0/{course_id}/
    GET api/course-structure/v0/{course_id}/?inherited_metadata=true&inherited_metadata_default=true

    **Example GET Response**

    The API will return 200, 404 response codes

    A 404 would be returned if course ID is invalid or course not found
    A 200 response would look something like
    {
      "$block_url": {
        "category": "$block_category",
        "children": [$block_children_urls... ],
        "metadata": {$block_metadata}
      },
      "$block_url": ....
    }


    """  # noqa: E501

    http_method_names = ["get"]
    permission_classes = [
        IsAdminUser,
    ]

    @verify_course_exists()
    def get(self, request, course_id):
        """
        Return the structure of a course as a JSON object
        """
        store = modulestore()

        try:
            course_key = CourseKey.from_string(course_id)
        except InvalidKeyError:
            raise DeveloperErrorViewMixin.api_error(  # noqa: B904, TRY200
                status_code=status.HTTP_404_NOT_FOUND,
                developer_message="Invalid course_id",
            )

        course = store.get_course(course_key)
        if course is None:
            raise DeveloperErrorViewMixin.api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                developer_message="Course not found",
            )

        # include inherited metadata
        inherited_metadata = request.GET.get("inherited_metadata", False)
        # include default values of inherited metadata
        inherited_metadata_default = request.GET.get(
            "inherited_metadata_default", False
        )

        # Precompute inherited metadata at the course level
        if inherited_metadata:
            compute_inherited_metadata(course)

        # Convert course data to dictionary and dump it as JSON
        json_data = dump_block(
            course,
            inherited=bool(inherited_metadata),
            defaults=bool(inherited_metadata_default),
        )

        return Response(json_data, status=status.HTTP_200_OK)
