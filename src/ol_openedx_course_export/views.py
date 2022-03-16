"""Views for Course Export"""

import logging

from cms.djangoapps.contentstore.api.views.course_import import (
    CourseImportExportViewMixin,
)
from cms.djangoapps.contentstore.tasks import CourseExportTask
from openedx.core.lib.api.view_utils import verify_course_exists
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from user_tasks.models import UserTaskStatus

from ol_openedx_course_export.tasks import task_upload_course_s3
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
    GET /api/courses/v0/export/{course_id}/?task_id={task_id}

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
        "upload_urls": {
            "course-v1:edX+DemoX+Demo_Course": "https://bucket_name.s3.amazonaws.com/course-v1:edX+DemoX+Demo_Course.tar.gz",
            "course-v1:edX+Test+Test_Course": "https://bucket_name.s3.amazonaws.com/course-v1:edX+Test+Test_Course.tar.gz"
        },
        "upload_task_ids": {
            "course-v1:edX+DemoX+Demo_Course"": "3f609080-3b68-460e-a660-473d7e6b096e",
            "course-v1:edX+Test+Test_Course": "bdae40e1-426a-4276-9409-020987545871"
        }
        "failed_uploads": {}
    }

    A 400 Will return in 2 cases:

    1 - There is an error with API parameters or AWS configuration. The response will be edX basic API error response

    2- When there is error in any or all passed course IDs related to uploading or generating a course OLX
        {
        "upload_urls": {
            "course-v1:edX+DemoX+Demo_Course": "https://bucket_name.s3.amazonaws.com/course-v1:edX+DemoX+Demo_Course.tar.gz",
        },
        "failed_uploads": {
            "course-v1:edX+Test+Test_Course": "Error message"
        }
    }

    **GET Parameters**

    A GET request must include the following parameters.

    * task_id: (required) The UUID of the task to check, e.g. "3f609080-3b68-460e-a660-473d7e6b096e"

    **GET Response Values**

        If the import task is found successfully by the UUID provided, an HTTP
        200 "OK" response is returned.

        The HTTP 200 response has the following values.

        * state: String description of the state of the task


    **Example GET Response**

        {
            "state": "Succeeded"
        }


    """

    http_method_names = ["get", "post"]
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

        course_upload_urls = {}
        failed_course_uploads = {}
        upload_task_ids = {}
        for course_id in course_ids:
            try:
                task_detail = task_upload_course_s3.delay(request.user.id, course_id)
                course_upload_urls[course_id] = get_aws_file_url(course_id)
                upload_task_ids[course_id] = task_detail.task_id
            except Exception as e:
                log.exception(f"Course export {course_id}: An error has occurred:")
                failed_course_uploads[course_id] = str(e)

        response_data = {
            "upload_urls": course_upload_urls,
            "upload_task_ids": upload_task_ids,
            "failed_uploads": failed_course_uploads,
        }

        if not failed_course_uploads:
            return Response(response_data, status=status.HTTP_200_OK)
        return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

    @verify_course_exists()
    def get(self, request, course_id):
        """
        Check the status of the specified task
        """
        try:
            task_id = request.GET["task_id"]
            args = {"course_key_string": course_id}
            name = CourseExportTask.generate_name(args)
            task_status = UserTaskStatus.objects.filter(
                name=name, task_id=task_id
            ).first()
            return Response({"state": task_status.state})
        except Exception as e:
            log.exception(str(e))
            raise self.api_error(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                developer_message=str(e),
                error_code="internal_error",
            )
