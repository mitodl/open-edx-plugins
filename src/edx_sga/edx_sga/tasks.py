"""celery async tasks"""
import zipfile
import hashlib
from io import BytesIO
import logging
import os
import shutil
import six

from django.conf import settings
from django.core.files.storage import default_storage  # lint-amnesty, pylint: disable=import-error
from django.core.files.base import ContentFile  # lint-amnesty, pylint: disable=import-error

from lms import CELERY_APP  # pylint: disable=no-name-in-module, import-error
from submissions import api as submissions_api  # lint-amnesty, pylint: disable=import-error
from student.models import user_by_anonymous_id  # lint-amnesty, pylint: disable=import-error
from opaque_keys.edx.locator import BlockUsageLocator

from edx_sga.constants import BLOCK_SIZE, ITEM_TYPE


log = logging.getLogger(__name__)
DATA_DIR = getattr(default_storage, "location", "/var/edxapp/uploads")
DEFAULT_FILE_STORAGE = getattr(settings, "DEFAULT_FILE_STORAGE", "django.core.files.storage.FileSystemStorage")


def is_s3_default_storage():
    """
    returns true if s3 is default storage.
    """
    return True if DEFAULT_FILE_STORAGE and "s3boto" in DEFAULT_FILE_STORAGE else False


def is_local_storage():
    """
    returns true if local storage is default storage.
    """
    return True if DEFAULT_FILE_STORAGE and "FileSystemStorage" in DEFAULT_FILE_STORAGE else False


def _collect_student_submissions(block_id, course_id, locator, destination_path):
    """
    prepare files for download

    Args:
        course_id (unicode): edx course id
        block_id (unicode): edx block id
        locator (BlockUsageLocator): BlockUsageLocator for the sga module
        destination_path (str): folder from where we will zip files and facilitate for download
    """

    submissions = submissions_api.get_all_submissions(
        course_id,
        block_id,
        ITEM_TYPE
    )
    for submission in submissions:
        answer = submission['answer']
        if answer:
            student = user_by_anonymous_id(submission['student_id'])
            ext = os.path.splitext(answer['filename'])[1]
            source_file_path = six.u('{loc.org}/{loc.course}/{loc.block_type}/{loc.block_id}/{sha1}{ext}').format(
                loc=locator,
                sha1=answer['sha1'],
                ext=ext
            )

            destination_file_path = _get_destination_file_path(
                student.username,
                answer['sha1'],
                ext,
                destination_path
            )
            try:
                default_storage.save(destination_file_path, ContentFile(b''))
                with default_storage.open(source_file_path, 'rb') as source_file_pointer, \
                        default_storage.open(destination_file_path, 'wb') as dest_file_pointer:
                    shutil.copyfileobj(source_file_pointer, dest_file_pointer, length=BLOCK_SIZE)
            except IOError:
                log.exception("Unable to download submission of student=%s", student.username)


def _get_destination_file_path(student_name, sha1, ext, destination_path):
    """
    return destination file path

    Args:
        student_name (str): user name of student
        sha1 (str): SHA code for file
        ext (str): extension of file
        destination_path (str): path (including name) of folder/file which we want to compress.
    """
    destination_file_name = six.u("{student_name}_{sha1}{ext}").format(
        student_name=student_name,
        sha1=sha1,
        ext=ext
    )
    return os.path.join(
        destination_path, destination_file_name
    )


def _compress_folder(destination_path, zip_file_path):
    """
    compress given folder/file

    Args:
        destination_path (str): path (including name) of folder/file which we want to compress.
    """
    if is_s3_default_storage():
        # create zip on s3 bucket
        zip_file_bytes = BytesIO()
        with zipfile.ZipFile(zip_file_bytes, 'w') as zip_pointer:
            for filename in default_storage.listdir(destination_path)[1]:
                destination_file_path = os.path.join(destination_path, filename)
                with default_storage.open(destination_file_path, 'rb') as destination_file:
                    zip_pointer.writestr(filename, destination_file.read())
        zip_file_bytes.seek(0)
        with default_storage.open(zip_file_path, 'wb') as zip_file_pointer:
            shutil.copyfileobj(zip_file_bytes, zip_file_pointer, length=BLOCK_SIZE)
    else:
        folder_path = os.path.join(DATA_DIR, destination_path)
        shutil.make_archive(
            folder_path,
            'zip',
            folder_path
        )


def _get_submissions_base_name(username, block_id, course_id):
    """
    returns submission folder name where we are saving files.

    Args:
        course_id (unicode): edx course id
        block_id (unicode): edx block id
        username (unicode): staff user name
    """
    return "{username}_submissions_{id}_{course_key}".format(
        username=username,
        id=hashlib.md5(block_id).hexdigest(),
        course_key=course_id
    )


def _get_submissions_dir_path(submissions_dir_name, locator):
    """
    returns directory path where we are saving files.

    Args:
        submissions_dir_name (str): name of folder
        locator (BlockUsageLocator): BlockUsageLocator for the sga module
    """
    return "{loc.org}/{loc.course}/{loc.run}/{submissions_dir_name}".format(
        loc=locator,
        submissions_dir_name=submissions_dir_name
    )


def _remove_existing_artifacts(destination_path):
    """
    removes existing submission collection folder and zip file.

    Args:
        destination_path (str): folder from where we will zip files and facilitate for download
    """
    # This try/except is needed because 'default_storage.exists' works for directory
    # paths using local file storage, but it always returns False using S3 file storage.
    # 'default_storage.listdir' throws an OSError if local file storage is being used and
    # the given directory doesn't exist, so this block attempts to iterate through the files
    # in the directory and ignores the OSError exception which indicates that the directory
    # doesn't exist.
    try:
        _, filenames = default_storage.listdir(destination_path)
        for filename in filenames:
            default_storage.delete(os.path.join(destination_path, filename))
    except OSError:
        pass
    zip_file_path = "{}.zip".format(destination_path)
    if default_storage.exists(zip_file_path):
        default_storage.delete(zip_file_path)


@CELERY_APP.task
def zip_student_submissions(course_id, block_id, locator_unicode, username):
    """
    Task to download all submissions as zip file

    Args:
        course_id (unicode): edx course id
        block_id (unicode): edx block id
        locator_unicode (unicode): Unicode representing a BlockUsageLocator for the sga module
        username (unicode): staff user name
    """
    locator = BlockUsageLocator.from_string(locator_unicode)
    submissions_dir_name = _get_submissions_base_name(username, block_id, course_id)
    relative_destination_path = _get_submissions_dir_path(submissions_dir_name, locator)
    _remove_existing_artifacts(relative_destination_path)
    _collect_student_submissions(block_id, course_id, locator, relative_destination_path)
    _compress_folder(
        relative_destination_path,
        get_zip_file_path(username, course_id, block_id, locator)
    )


def get_zip_file_name(username, block_id, course_id):
    """
    returns submission folder name where we are saving files temporary.

    Args:
        course_id (unicode): edx course id
        block_id (unicode): edx block id
        username (unicode): staff user name
    """
    submissions_dir_name = _get_submissions_base_name(username, block_id, course_id)
    return "{}.zip".format(submissions_dir_name)


def get_zip_file_path(username, course_id, block_id, locator):
    """
    returns zip file path.

    Args:
        username (unicode): user name
        course_id (unicode): edx course id
        block_id (unicode): edx block id
        locator (BlockUsageLocator): BlockUsageLocator for the sga module
    """
    return _get_submissions_dir_path(
        get_zip_file_name(
            username,
            block_id,
            course_id
        ),
        locator
    )
