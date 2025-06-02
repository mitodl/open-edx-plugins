import json
import logging
import subprocess

from django.conf import settings
from django.utils.translation import gettext as _
from path import Path as get_path  # noqa: N813
from rest_framework import permissions, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView

from edx_sysadmin.api.permissions import GithubWebhookPermission
from edx_sysadmin.git_import import (
    DEFAULT_GIT_REPO_DIR,
    add_repo,
)
from edx_sysadmin.utils.utils import (
    get_clean_branch_name,
    get_local_active_branch,
    get_local_course_repo,
)

logger = logging.getLogger(__name__)


class GitReloadAPIView(APIView):
    """
    APIView to reload courses from github on triggering github webhook
    """

    permission_classes = [GithubWebhookPermission]

    def post(self, request):
        """
        Trigger for github webhooks for course reload
        """
        err_msg = ""
        try:
            event = request.headers.get("X-Github-Event")
            payload = json.loads(request.body)
            repo_ssh_url = payload["repository"].get("ssh_url")
            repo_name = payload["repository"].get("name")
            pushed_branch = payload.get("ref", "")
            clean_pushed_branch = get_clean_branch_name(pushed_branch)

            if event != "push":
                err_msg = _("The API works for 'Push' events only")
            elif not repo_name:
                err_msg = _("Couldn't find Repo's name in the payload")
            elif not repo_ssh_url:
                err_msg = _("Couldn't find Repo's ssh_url in the payload")
            elif not pushed_branch:
                err_msg = _("Couldn't find Repo's pushed branch ref in the payload")
            elif (
                not hasattr(settings, "SYSADMIN_DEFAULT_BRANCH")
                or settings.SYSADMIN_DEFAULT_BRANCH is None
            ):
                err_msg = _("SYSADMIN_DEFAULT_BRANCH is not configured in settings")
            elif clean_pushed_branch != settings.SYSADMIN_DEFAULT_BRANCH:
                err_msg = _(
                    "Couldn't reload course from the branch ({}), expected branch was ({}) "  # noqa: E501
                ).format(clean_pushed_branch, settings.SYSADMIN_DEFAULT_BRANCH)
            else:
                repo = get_local_course_repo(repo_name)
                if not repo:
                    # New course reload trigger received from a repo but we don't have
                    # it's local copy. We will do the course import instead of reload

                    add_repo.delay(
                        repo=repo_ssh_url, branch=settings.SYSADMIN_DEFAULT_BRANCH
                    )
                    msg = _(
                        "No local course copy found. Triggered course import from branch: {} of repo: {}"  # noqa: E501
                    ).format(settings.SYSADMIN_DEFAULT_BRANCH, repo_name)
                    return self.get_reload_response(
                        msg=msg, status_code=status.HTTP_200_OK
                    )

                else:
                    # We have an existing local copy of the course, so we will reload
                    # the course after making sure that the reload trigger is from the
                    # same branch that was used to import the course initially
                    active_branch = get_local_active_branch(repo)
                    if not active_branch or active_branch != pushed_branch:
                        err_msg = _(
                            "The pushed branch ({}) is not currently in use"
                        ).format(pushed_branch)
                    else:
                        add_repo.delay(repo_ssh_url)
                        msg = _("Triggered reloading branch: {} of repo: {}").format(
                            active_branch, repo_name
                        )
                        return self.get_reload_response(
                            msg=msg, status_code=status.HTTP_200_OK
                        )
        except Exception as e:
            err_msg = str(e)
            logger.exception(f"{self.__class__.__name__}:: {err_msg}")  # noqa: G004

        return self.get_reload_response(
            msg=err_msg, status_code=status.HTTP_400_BAD_REQUEST
        )

    def get_reload_response(self, msg, status_code):
        if status_code == status.HTTP_200_OK:
            logger.info(f"{self.__class__.__name__}:: {msg}")  # noqa: G004
        else:
            logger.info(f"{self.__class__.__name__}:: {msg}")  # noqa: G004

        return Response(
            {"message": msg},
            status=status_code,
        )


class GitCourseDetailsAPIView(APIView):
    """
    APIView to get git related details of list of courses
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        """
        Get git related details of list of courses
        """
        try:
            course_dir = request.GET.get("courseDir")
            if course_dir:
                return Response(
                    self.git_info_for_course(course_dir),
                    status=status.HTTP_200_OK,
                )
            else:
                err_msg = "Course directory name is required"

        except Exception as e:  # noqa: BLE001
            err_msg = str(e)

        logger.exception(f"{self.__class__.__name__}:: {err_msg}")  # noqa: G004
        return Response(
            {"message": err_msg},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def git_info_for_course(self, course_dir):
        """
        Pull out some git info like the last commit
        """

        git_dir = settings.DATA_DIR / course_dir

        # Try the data dir, then try to find it in the git import dir
        if not git_dir.exists():
            git_repo_dir = getattr(settings, "GIT_REPO_DIR", DEFAULT_GIT_REPO_DIR)
            git_dir = get_path(git_repo_dir) / course_dir
            if not git_dir.exists():
                return ["", "", ""]

        cmd = [
            "git",
            "log",
            "-1",
            '--format=format:{ "commit": "%H", "author": "%an %ae", "date": "%ad"}',
        ]
        try:
            output_json = json.loads(
                subprocess.check_output(cmd, cwd=git_dir).decode("utf-8")  # noqa: S603
            )
        except OSError as error:
            logger.warning("Error fetching git data: %s - %s", course_dir, error)
            raise
        except (ValueError, subprocess.CalledProcessError):
            raise

        return output_json
