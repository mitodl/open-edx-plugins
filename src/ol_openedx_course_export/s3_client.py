import boto3
from django.conf import settings

from ol_openedx_course_export.utils import get_file_name_with_extension


class S3Client:
    client = None

    def __init__(self):
        if not self.client:
            self.client = self.get_s3_client()

    def get_s3_client(self):
        return boto3.resource(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )

    def upload_course_s3(self, course_tar, course_id):
        self.client.Bucket(settings.COURSE_IMPORT_EXPORT_BUCKET).put_object(
            Key=f"{get_file_name_with_extension(course_id)}", Body=course_tar
        )

    def get_bucket_url(self):
        """Returns a URL for the bucket, which is then used to add in the API response"""
        return self.client.get_bucket_location(
            Bucket=settings.COURSE_IMPORT_EXPORT_BUCKET
        )
