import logging

import requests
from cms.djangoapps.models.settings.course_metadata import CourseMetadata
from crum import get_current_request
from django.conf import settings
from django.dispatch import receiver
from django.template.defaultfilters import slugify
from ol_openedx_git_auto_export.constants import (
    ENABLE_AUTO_GITHUB_REPO_CREATION,
    ENABLE_GIT_AUTO_EXPORT,
)
from ol_openedx_git_auto_export.tasks import async_export_to_git
from openedx_events.content_authoring.signals import COURSE_CREATED
from xmodule.modulestore.django import SignalHandler, modulestore

from .utils import get_or_create_git_export_repo_dir

log = logging.getLogger(__name__)


@receiver(SignalHandler.course_published)
def listen_for_course_publish(
    sender,  # noqa: ARG001
    course_key,
    **kwargs,  # noqa: ARG001
):  # pylint: disable=unused-argument
    """
    Receives publishing signal and performs publishing related workflows
    """
    get_or_create_git_export_repo_dir()

    if settings.FEATURES.get("ENABLE_EXPORT_GIT") and settings.FEATURES.get(
        ENABLE_GIT_AUTO_EXPORT
    ):
        # If the Git auto-export is enabled, push the course changes to Git
        log.info(
            "Course published with auto-export enabled. Starting export... (course id: %s)",  # noqa: E501
            course_key,
        )
        async_export_to_git.delay(str(course_key))


@receiver(COURSE_CREATED)
def listen_for_course_created(**kwargs):
    course_id = kwargs.get("course").course_key
    course_id_slugified = slugify(str(course_id))
    store = modulestore()
    course_module = store.get_course(course_id, depth=0)
    user = get_current_request().user
    if not settings.FEATURES.get(ENABLE_AUTO_GITHUB_REPO_CREATION):
        log.info(
            "GitHub repo creation is disabled. Skipping GitHub repo creation for course %s",
            course_id,
        )
        return

    gh_access_token = settings.GITHUB_ACCESS_TOKEN
    if not settings.GITHUB_ORG_API_URL or not gh_access_token:
        log.error(
            "GITHUB_ORG_API_URL or GITHUB_ACCESS_TOKEN is not set in settings. Skipping GitHub repo creation."
        )
        return

    url = f"{settings.GITHUB_ORG_API_URL}/repos"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {gh_access_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "name": course_id_slugified,
        "description": f"Git repository for {course_id!s}",
        "private": True,
        "has_issues": False,
        "has_project": False,
        "has_wiki": False,
        "auto_init": True,
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 201:
        log.error(
            "Failed to create GitHub repository for course %s: %s",
            course_id,
            response.json(),
        )
        return

    repo_data = response.json()
    ssh_url = repo_data.get("ssh_url")
    if ssh_url:
        CourseMetadata.validate_and_update_from_json(
            course_module,
            {
                "giturl": {"value": ssh_url},
            },
            user,
        )
        store.update_item(course_module, user.id)
        log.info(
            "GitHub repository created for course %s: %s",
            course_id,
            ssh_url,
        )
    else:
        log.error(
            "Failed to retrieve URL for GitHub repository for course %s",
            course_id,
        )
        return
