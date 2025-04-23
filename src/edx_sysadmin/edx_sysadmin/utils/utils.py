"""
Utility function defined here.
"""

# pylint: disable=wrong-import-order
import json
import logging
import os
import urllib.parse

import requests
from common.djangoapps.student.models import UserProfile
from common.djangoapps.student.roles import CourseInstructorRole
from common.djangoapps.util.password_policy_validators import normalize_password
from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import Http404
from django.urls import reverse
from django.utils.translation import gettext as _
from django_countries import countries
from git import InvalidGitRepositoryError, NoSuchPathError, Repo
from openedx.core.djangoapps.user_authn.toggles import (
    is_require_third_party_auth_enabled,
)
from xmodule.modulestore.django import modulestore

from edx_sysadmin.models import CourseGitLog
from edx_sysadmin.utils.markup import HTML, Text

User = get_user_model()
logger = logging.getLogger(__name__)

DEFAULT_GIT_REPO_PREFIX = "refs/heads/"


def get_course_by_id(course_key, depth=0):
    """
    Given a course id, return the corresponding course descriptor.

    If such a course does not exist, raises a 404.

    depth: The number of levels of children for the modulestore to cache. None means infinite depth
    """  # noqa: E501
    with modulestore().bulk_operations(course_key):
        course = modulestore().get_course(course_key, depth=depth)
    if course:
        return course
    else:
        msg = f"{_('Course not found')}: {course_key}"
        raise Http404(msg)


def get_registration_required_extra_fields():
    """
    Process and return a list of extra fields which are required for User account
    registration through Registration API "/user_api/v1/account/registration/",
    depending upon "settings.REGISTRATION_EXTRA_FIELDS" environment setting

    Arguments:
    None

    Returns:
    extra_fields (list) - list of required fields
    from "settings.REGISTRATION_EXTRA_FIELDS"
    """
    extra_fields = []
    for field, status in settings.REGISTRATION_EXTRA_FIELDS.items():
        if status == "required":
            extra_fields.append(field)
    return extra_fields


def get_registration_required_extra_fields_with_values():
    """
    Map registration required extra fields with some pre-defined default values to
    create django form fields dynamically

    Arguments:
    None

    Returns:
    extra_fields (dict) - contains all required fields and their mapping with default
    values and form type.
    {
        ...
        "FIELD_NAME": {
            "field_type": "FIELD_TYPE",
            "default_value": "DEFAULT_VALUE",     # if applicable
            "choices": "LIST_OF_OPTIONS"          # if applicable
        }
        ...
    }
    """
    extra_fields = {}

    # If Registration API is not functional we can't use it,
    # so no need to process extra fields.
    if is_registration_api_functional():
        fields_and_default_values_map = get_fields_and_default_values_map()
        for field in get_registration_required_extra_fields():
            mapping = fields_and_default_values_map.get(field)
            if mapping:
                extra_fields[field] = mapping
    return extra_fields


def is_registration_api_functional():
    """
    Check if User Registration API "/user_api/v1/account/registration/" is functional
    or not depending upon two environment variables
    "settings.FEATURES['ALLOW_PUBLIC_ACCOUNT_CREATION']" and
    "settings.ENABLE_REQUIRE_THIRD_PARTY_AUTH"

    Arguments:
    None

    Returns:
    Boolean - True if User Registration API "/user_api/v1/account/registration/"
    is functional.
    """
    if (  # noqa: SIM103
        settings.FEATURES["ALLOW_PUBLIC_ACCOUNT_CREATION"]
        and not is_require_third_party_auth_enabled()
    ):
        return True
    return False


def create_user_account(data, use_reg_api=True):  # noqa: FBT002
    """
    Create User Account through "/user_api/v1/account/registration/" API (if available)
    or directly through "User" and "UserProfile" models

    Arguments:
    data (dict) - the params to use while creating user account,
        it can have "username", "name", "email", "password" and
        many other registration related fields

    use_reg_api (boolean) - used to specify which account creation
        flow should be followed.

    Returns:
    context (dict) - having context to be passed to templates having information
        about success and failure of account creation.
    """
    context = {}
    if is_registration_api_functional() and use_reg_api:
        context = make_reg_api_request(data=data)
    else:
        context = create_user_through_db_models(data)

    return context


def create_user_through_db_models(data):
    """
    Register User through database models

    Arguments:
    data (dict) - User account details

    Returns:
    context (dict) - context to be passed to templates having information about success
        and failure of account creation
    """
    context = {}
    try:
        if not User.objects.filter(email=data["email"]).exists():
            user = User(username=data["username"], email=data["email"], is_active=True)
            password = normalize_password(data["password"])
            user.set_password(password)
            user.save()

            profile = UserProfile(user=user)
            profile.name = data.get("name")
            profile.save()

            context["success_message"] = (
                f"{_('A new account has been registered for user')}: {data['username']}"
            )
        else:
            context["error_message"] = (
                f"{_('An account already exists with email')}: {data['email']}"
            )
            return context
    except Exception as err:  # noqa: BLE001
        context["error_message"] = (
            f"{_('Account could not be created due to following error')}: {err}"
        )

    return context


def make_reg_api_request(data):
    """
    Make POST request to "/user_api/v1/account/registration/" API to register User

    Arguments:
    data (dict) - User account details

    Returns:
    context (dict) - context to be passed to templates having information
        about success and failure of account creation
    """
    context = {}

    api_endpoint = urllib.parse.urljoin(
        get_lms_root_url(), reverse("user_api_registration")
    )
    resp = requests.post(api_endpoint, data=data)  # noqa: S113

    if resp.status_code == 200:  # noqa: PLR2004
        context["success_message"] = (
            f"{_('A new account has been registered through API for user')}: {data.get('username')}"  # noqa: E501
        )
    else:
        context["error_message"] = (
            f"{_('Account could not be created due to following error(s)')}: {transform_error_message(resp.content)}"  # noqa: E501
        )

    return context


def get_lms_root_url():
    """
    Return LMS Root URL of edx-platform

    Returns:
    url (str) - LMS Root URL
    """
    return settings.LMS_ROOT_URL


def transform_error_message(resp_content):
    """
    Transform Registration API error messages

    Arguments:
    resp_content (response.content) - Response object's content

    Returns:
    message (str) - A string of formatted errors
    """
    content = json.loads(resp_content.decode("utf-8").replace("\n", ""))
    message = ""
    for error_key, error_content in content.items():
        if error_content:
            error_message = (
                str(error_content[0].get("user_message"))
                if isinstance(error_content, list)
                else error_content
            )
            message += Text("{li_start} {error_key}: {error_content} {li_end}").format(
                li_start=HTML("<li>"),
                error_key=error_key,
                error_content=error_message,
                li_end=HTML("</li>"),
            )
    return Text("{ul_start} {message} {ul_end}").format(
        ul_start=HTML("<ul>"), message=message, ul_end=HTML("</ul>")
    )


def get_level_of_education_choices():
    """
    List of "Level of Education" choices provided by UserProfile
    """
    return list(UserProfile.LEVEL_OF_EDUCATION_CHOICES)


def get_gender_choices():
    """
    List of "Gender" choices provided by UserProfile
    """
    return list(UserProfile.GENDER_CHOICES)


def get_valid_year_of_birth_choices():
    """
    List of valid "Year of Birth" choices provided by UserProfile
    """
    return [(year, year) for year in UserProfile.VALID_YEARS]


def get_country_choices():
    """
    List of "Country" choices
    """
    return list(countries)


def get_fields_and_default_values_map():
    """
    Map registration required extra fields with some pre-defined default values

    Arguments:
    None

    Returns:
    fields_and_default_values_map (dict) - contains all required fields and their
    mapping with default values.
    and form type.
    {
        ...
        "FIELD_NAME": {
            "field_type": "FIELD_TYPE",
            "default_value": "DEFAULT_VALUE",     # if applicable
            "choices": "LIST_OF_OPTIONS"          # if applicable
        }
        ...
    }
    """
    return {
        "level_of_education": {
            "field_type": forms.TypedChoiceField,
            "choices": get_level_of_education_choices(),
        },
        "gender": {
            "field_type": forms.TypedChoiceField,
            "choices": get_gender_choices(),
        },
        "year_of_birth": {
            "field_type": forms.TypedChoiceField,
            "choices": get_valid_year_of_birth_choices(),
        },
        "mailing_address": {
            "field_type": forms.CharField,
            "default_value": "",
        },
        "goals": {
            "field_type": forms.CharField,
            "default_value": "",
        },
        "honor_code": {"field_type": forms.BooleanField, "default_value": False},
        "terms_of_service": {"field_type": forms.BooleanField, "default_value": False},
        "city": {"field_type": forms.CharField, "default_value": ""},
        "country": {
            "field_type": forms.TypedChoiceField,
            "choices": get_country_choices(),
        },
    }


def user_has_access_to_sysadmin(user):
    """
    Check if user has access to sysadmin panel or not
    :param user: User object of currently loggedin user
    :return boolean: True if user has access to syadmin else False
    """
    if (  # noqa: SIM103
        user_has_access_to_users_panel(user)
        or user_has_access_to_courses_panel(user)
        or user_has_access_to_git_logs_panel(user)
        or user_has_access_to_git_import_panel(user)
    ):
        return True
    return False


def show_sysadmin_dashboard(user):
    """
    Check if all the requirements for showing edx-sysadmin are fulfilled
    :return boolean: True if all requirements are fulfilled else False
    """
    return user_has_access_to_sysadmin(user)


def user_has_access_to_users_panel(user):
    """
    Check if user has access to "Users" panel or not
    :param user: User object of currently loggedin user
    :return boolean: True if user has access to "Users" panel else False
    """
    if user and user.is_staff:  # noqa: SIM103
        return True
    return False


def user_has_access_to_courses_panel(user):
    """
    Check if user has access to "Courses" panel or not
    :param user: User object of currently loggedin user
    :return boolean: True if user has access to "Courses" panel else False
    """
    if user and user.is_staff:  # noqa: SIM103
        return True
    return False


def user_has_access_to_git_logs_panel(user):
    """
    Check if user has access to "Git Logs" panel or not
    :param user: User object of currently loggedin user
    :return boolean: True if user has access to "Git Logs" panel else False
    """
    if user and (  # noqa: SIM103
        user.is_staff
        or user.courseaccessrole_set.filter(role=CourseInstructorRole.ROLE).exists()
    ):
        return True
    return False


def user_has_access_to_git_import_panel(user):
    """
    Check if user has access to "Git Import" panel or not
    :param user: User object of currently loggedin user
    :return boolean: True if user has access to "Git Import" panel else False
    """
    if user and user.is_staff:  # noqa: SIM103
        return True
    return False


def remove_old_course_import_logs(course_id):
    """
    Remove old CourseGitLog if the log count increases the
    settings.SYSADMIN_MAX_GIT_LOGS_THRESHOLD.

    :param course_id: CourseLocation object to target specific logs
    :return int: Count of deleted logs if anything gets deleted else 0
    """
    if hasattr(settings, "SYSADMIN_MAX_GIT_LOGS_THRESHOLD") and isinstance(
        settings.SYSADMIN_MAX_GIT_LOGS_THRESHOLD, int
    ):
        threshold = settings.SYSADMIN_MAX_GIT_LOGS_THRESHOLD
        deletion_count, _ = CourseGitLog.objects.filter(
            id__in=list(
                CourseGitLog.objects.filter(course_id=course_id)
                .order_by("-created")
                .values_list("id", flat=True)[threshold:]
            )
        ).delete()

        return deletion_count
    else:
        return 0


def get_local_course_repo(repo_name):
    """
    Get local course repo
    :param repo_name: course repo name to be fetched from local repos directory
    :return git.Repo: git course repo object else None
    """
    if os.path.isdir(settings.GIT_REPO_DIR) and repo_name:  # noqa: PTH112
        try:
            return Repo(os.path.join(settings.GIT_REPO_DIR, repo_name))  # noqa: PTH118
        except (
            InvalidGitRepositoryError,
            NoSuchPathError,
        ) as e:
            logger.exception(str(e))  # noqa: TRY401
            return None
    return None


def get_local_active_branch(repo):
    """
    Get active branch of a git repo
    :params repo (git.Repo object): course repo
    :return str: active branch name of repo else None
    """
    try:
        if repo:
            return repo.active_branch.path
    except TypeError:
        logger.exception("Unable to get current branch of checked out repo")
        return None


def get_clean_branch_name(branch_name):
    """
    Get a clean branch name from pushed branch of a webhook payload
    :params branch_name (str): Branch name with format `refs/heads/<branch_name>`
    :return str: Clean branch name without `refs/heads/<branch_name>`
    """

    return branch_name.replace(DEFAULT_GIT_REPO_PREFIX, "")
