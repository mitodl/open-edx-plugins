import logging
import os
from django.conf import settings

log = logging.getLogger(__name__)


def get_or_create_git_export_repo_dir():
    git_repo_export_dir = getattr(
        settings, "GIT_REPO_EXPORT_DIR", "/edx/var/edxapp/export_course_repos"
    )
    if not os.path.exists(git_repo_export_dir):  # noqa: PTH110
        # for development/docker/vagrant if GIT_REPO_EXPORT_DIR folder does not exist then create it  # noqa: E501
        log.error(
            "GIT_REPO_EXPORT_DIR is not available in settings, please create it first"
        )
        os.makedirs(git_repo_export_dir, 0o755)  # noqa: PTH103

    return git_repo_export_dir
