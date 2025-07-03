from django.conf import settings

from ol_openedx_course_export.constants import AWS_S3_DEFAULT_URL_PREFIX


def is_bucket_configuration_valid():
    """
    For course export to work properly we need all the AWS settings configured properly
    """
    return (
        settings.COURSE_IMPORT_EXPORT_BUCKET is not None
        and settings.COURSE_IMPORT_EXPORT_BUCKET.strip() != ""
    )


def get_file_name_with_extension(course_id):
    """
    Args:
        course_id: (str) course_id of the generated course tarball/OLX file
        e.g. 'course-v1:edX+DemoX+Demo_Course'
    Returns:
        str: Returns the file name with file extension suffix .tar.gz
    """
    return course_id + ".tar.gz"


def get_aws_file_url(course_id):
    """
    Args:
        course_id: (str) course_id of the generated course tarball/OLX file
        e.g. 'course-v1:edX+DemoX+Demo_Course'
    Returns:
        str: Returns the S3 specific access URL for the file
    """

    return f"https://{settings.COURSE_IMPORT_EXPORT_BUCKET}.{AWS_S3_DEFAULT_URL_PREFIX}/{get_file_name_with_extension(course_id)}"
