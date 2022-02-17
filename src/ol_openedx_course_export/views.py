"""Views for Course Export"""

import logging

from botocore.exceptions import ClientError
from cms.djangoapps.contentstore.api.views.course_import import (
    CourseImportExportViewMixin,
)
from cms.djangoapps.contentstore.tasks import create_export_tarball
from opaque_keys.edx.keys import CourseKey
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from xmodule.modulestore.django import modulestore

from ol_openedx_course_export.s3_client import S3Client
from ol_openedx_course_export.utils import (
    get_aws_file_url,
    is_bucket_configuration_valid,
)

log = logging.getLogger(__name__)


class CourseExportView(CourseImportExportViewMixin, GenericAPIView):
    """
    An API View to export courses to S3 buckets instead of local storage

    **Example Requests**

    POST /api/courses/v0/export/

    **POST Parameters**

    A POST request must include a JSON list of course Ids to be exported
    e.g. A sample payload might look like below:
    {
        "courses": ["course-v1:edX+DemoX+Demo_Course", "course-v1:edX+Test+Test_Course"]
    }

    **Example POST Response**
    The API will return two types of response codes in general
    200, 400

    A 200 with successful_uploads when all the passed courses IDs were uploaded successfully

    {
        "successful_uploads": {
            "course-v1:edX+DemoX+Demo_Course": "https://bucket_name.s3.amazonaws.com/course-v1:edX+DemoX+Demo_Course.tar.gz",
            "course-v1:edX+Test+Test_Course": "https://bucket_name.s3.amazonaws.com/course-v1:edX+Test+Test_Course.tar.gz"
        },
        "failed_uploads": {}
    }

    A 400 Will return in 2 cases:

    1 - There is an error with API parameters or AWS configuration. The response will be edX basic API error response

    2- When there is error in any or all passed course IDs related to uploading or generating a course OLX
        {
        "successful_uploads": {
            "course-v1:edX+DemoX+Demo_Course": "https://bucket_name.s3.amazonaws.com/course-v1:edX+DemoX+Demo_Course.tar.gz",
        },
        "failed_uploads": {
            "course-v1:edX+Test+Test_Course": "Error message"
        }
    }

    """

    http_method_names = ["post"]
    permission_classes = [
        IsAdminUser,
    ]

    def post(self, request):
        """
        This will take list of course id as param and will export them to S3
        """
        if not is_bucket_configuration_valid():
            raise self.api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                developer_message="COURSE_IMPORT_EXPORT_BUCKET value is not configured properly",
                error_code="internal_error",
            )

        # Course Ids of the courses to be uploaded
        course_ids = request.data.get("courses", [])
        if not course_ids:
            raise self.api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                developer_message="No course Id was provided",
                error_code="internal_error",
            )

        successful_course_uploads = {}
        failed_course_uploads = {}
        s3_client = S3Client()

        for course_id in course_ids:
            try:
                course_key = CourseKey.from_string(course_id)
                module_store = modulestore()
                course_module = module_store.get_course(course_key)
                course_tarball = create_export_tarball(
                    course_module, course_key, {}, None
                )
                s3_client.upload_course_s3(
                    course_tar=course_tarball, course_id=course_id
                )
                successful_course_uploads[course_id] = get_aws_file_url(course_id)

            except ClientError as e:
                log.exception(
                    f"Course export {course_id}: A ClientError in course export:"
                )
                failed_course_uploads[course_id] = str(e)

            except Exception as e:
                log.exception(f"Course export {course_id}: An Error in course export:")
                failed_course_uploads[course_id] = str(e)

        response_data = {
            "successful_uploads": successful_course_uploads,
            "failed_uploads": failed_course_uploads,
        }

        if not failed_course_uploads:
            return Response(response_data, status=status.HTTP_200_OK)
        return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
