"""Tests for the ROLE_ASSIGNMENT_CREATED signal handler."""

from unittest import mock

import pytest
from django.test import override_settings
from ol_openedx_events_handler.handlers.role_assignment import (
    handle_role_assignment_created,
)

# The signal these tests exercise arrived in openedx-events 11.2.0, which is
# the condition apps.py checks before registering the receiver. The handler
# also reads scope types and namespaces from openedx-authz, and the version a
# release pinning older openedx-events ships (Ulmo: 0.20.0) predates those, so
# both are required here and the module skips rather than fails without them.
pytest.importorskip("openedx_events.authz.data")
pytest.importorskip("openedx_authz.api.data")

VALID_WEBHOOK_PATCH = mock.patch(
    "ol_openedx_events_handler.utils.validate_enrollment_webhook",
    return_value=True,
)
TASK_PATCH = mock.patch(
    "ol_openedx_events_handler.tasks.notify_course_access_role_addition"
)
COURSE_KEY = "course-v1:OpenedX+DemoX+DemoCourse"
DEFAULT_ROLES = ["instructor", "staff"]
USERNAME = "course-team-member"
EMAIL = "course-team-member@example.com"


def _event(
    *,
    subject=f"user^{USERNAME}",
    role="role^course_staff",
    scope=f"course-v1^{COURSE_KEY}",
):
    """Build a RoleAssignmentData as openedx-authz emits it."""
    from openedx_events.authz.data import RoleAssignmentData  # noqa: PLC0415

    return RoleAssignmentData(
        operation="created",
        subject=subject,
        role=role,
        scope=scope,
        actor_id=None,
    )


@pytest.fixture
def team_member(django_user_model):
    """A user holding the course team role."""
    return django_user_model.objects.create(username=USERNAME, email=EMAIL)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("authz_role", "expected_legacy_role"),
    [
        ("course_staff", "staff"),
        ("course_admin", "instructor"),
    ],
)
@VALID_WEBHOOK_PATCH
@TASK_PATCH
def test_dispatches_for_a_course_team_role(
    mock_task,
    _mock_validate,  # noqa: PT019
    authz_role,
    expected_legacy_role,
    team_member,  # noqa: ARG001
):
    """
    An authz course team role is sent under its legacy name.

    The consumer and ENROLLMENT_COURSE_ACCESS_ROLES both speak the legacy
    names, so the authz name is translated rather than passed through.
    """
    with override_settings(ENROLLMENT_COURSE_ACCESS_ROLES=DEFAULT_ROLES):
        handle_role_assignment_created(
            None, role_assignment=_event(role=f"role^{authz_role}")
        )

    mock_task.delay.assert_called_once_with(
        user_email=EMAIL,
        course_key=COURSE_KEY,
        role=expected_legacy_role,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("label", "scope"),
    [
        ("a content library", "lib^lib:OpenedX:demo"),
        ("an organization", "org^OpenedX"),
        ("no namespace at all", "garbage"),
        ("every course in an org", "course-v1^course-v1:OpenedX+DemoX+*"),
        ("every course on the platform", "course-v1^course-v1:*+*+*"),
        # CCXCourseOverviewData subclasses CourseOverviewData, so an isinstance
        # test would send this CCX locator to a consumer that records runs.
        ("a CCX run", "ccx-v1^ccx-v1:OpenedX+DemoX+DemoCourse+ccx@1"),
        ("a course namespace that does not parse", "course-v1^not-a-course-key"),
        ("an empty scope", ""),
    ],
)
@VALID_WEBHOOK_PATCH
@TASK_PATCH
def test_ignores_assignments_that_are_not_on_a_course(
    mock_task,
    _mock_validate,  # noqa: PT019
    label,  # noqa: ARG001
    scope,
    team_member,  # noqa: ARG001
):
    """Only course scopes are mirrored; the consumer keys records on a run."""
    with override_settings(ENROLLMENT_COURSE_ACCESS_ROLES=DEFAULT_ROLES):
        handle_role_assignment_created(None, role_assignment=_event(scope=scope))

    mock_task.delay.assert_not_called()


@pytest.mark.django_db
@VALID_WEBHOOK_PATCH
@TASK_PATCH
def test_ignores_a_role_with_no_legacy_equivalent(
    mock_task,
    _mock_validate,  # noqa: PT019
    team_member,  # noqa: ARG001
):
    """A role that does not map to a course access role is not sent."""
    with override_settings(ENROLLMENT_COURSE_ACCESS_ROLES=DEFAULT_ROLES):
        handle_role_assignment_created(
            None, role_assignment=_event(role="role^library_admin")
        )

    mock_task.delay.assert_not_called()


@pytest.mark.django_db
@VALID_WEBHOOK_PATCH
@TASK_PATCH
def test_respects_the_allowed_roles_setting(
    mock_task,
    _mock_validate,  # noqa: PT019
    team_member,  # noqa: ARG001
):
    """The setting is matched on the legacy name, not the authz one."""
    with override_settings(ENROLLMENT_COURSE_ACCESS_ROLES=["instructor"]):
        handle_role_assignment_created(None, role_assignment=_event())

    mock_task.delay.assert_not_called()


@pytest.mark.django_db
@VALID_WEBHOOK_PATCH
@TASK_PATCH
def test_skips_a_subject_that_is_not_a_known_user(
    mock_task,
    _mock_validate,  # noqa: PT019
):
    """
    A user^ subject with no matching account is skipped rather than raising.

    No team_member fixture here, so the username resolves to nobody and the
    handler takes the DoesNotExist branch. A subject under another namespace
    never reaches that lookup; those have their own tests below.
    """
    with override_settings(ENROLLMENT_COURSE_ACCESS_ROLES=DEFAULT_ROLES):
        handle_role_assignment_created(
            None, role_assignment=_event(subject="user^nobody")
        )

    mock_task.delay.assert_not_called()


@pytest.mark.django_db
@VALID_WEBHOOK_PATCH
@TASK_PATCH
def test_skips_a_non_user_subject_named_after_an_existing_user(
    mock_task,
    _mock_validate,  # noqa: PT019
    team_member,  # noqa: ARG001
):
    """
    A subject in another namespace is skipped even when a user shares its name.

    The subject namespace decides this, not whether the lookup finds someone.
    Stripping the prefix and querying by the remainder would mirror a course
    team role onto an unrelated individual who happens to share the name.
    """
    with override_settings(ENROLLMENT_COURSE_ACCESS_ROLES=DEFAULT_ROLES):
        handle_role_assignment_created(
            None, role_assignment=_event(subject=f"sub^{USERNAME}")
        )

    mock_task.delay.assert_not_called()


@pytest.mark.django_db
@VALID_WEBHOOK_PATCH
@TASK_PATCH
def test_skips_a_role_key_in_the_wrong_namespace(
    mock_task,
    _mock_validate,  # noqa: PT019
    team_member,  # noqa: ARG001
):
    """
    A role key that does not carry the role namespace is not translated.

    Same reasoning as the subject case: the name after the separator may be
    a real role, but a key arriving under another namespace is malformed rather
    than a grant to act on.
    """
    with override_settings(ENROLLMENT_COURSE_ACCESS_ROLES=DEFAULT_ROLES):
        handle_role_assignment_created(
            None, role_assignment=_event(role=f"user^{USERNAME}")
        )

    mock_task.delay.assert_not_called()


@pytest.mark.django_db
@VALID_WEBHOOK_PATCH
@TASK_PATCH
def test_skips_when_the_allowed_roles_setting_is_absent(
    mock_task,
    _mock_validate,  # noqa: PT019
    team_member,  # noqa: ARG001
):
    """
    Nothing is mirrored when ENROLLMENT_COURSE_ACCESS_ROLES is not configured.

    An operator who has not opted a role in gets no webhook rather than every
    role. The settings object is replaced with one carrying no attributes at
    all, so this exercises the ``getattr`` default itself rather than depending
    on what the ambient test settings happen to define.
    """
    with (
        override_settings(ENROLLMENT_COURSE_ACCESS_ROLES=DEFAULT_ROLES),
        mock.patch(
            "ol_openedx_events_handler.handlers.role_assignment.settings",
            spec=[],
        ),
    ):
        handle_role_assignment_created(None, role_assignment=_event())

    mock_task.delay.assert_not_called()


@pytest.mark.django_db
@VALID_WEBHOOK_PATCH
@TASK_PATCH
def test_skips_a_user_with_no_email(
    mock_task,
    _mock_validate,  # noqa: PT019
    django_user_model,
):
    """The consumer identifies people by email, so one is required."""
    django_user_model.objects.create(username="no-email-user", email="")

    with override_settings(ENROLLMENT_COURSE_ACCESS_ROLES=DEFAULT_ROLES):
        handle_role_assignment_created(
            None, role_assignment=_event(subject="user^no-email-user")
        )

    mock_task.delay.assert_not_called()


@mock.patch(
    "ol_openedx_events_handler.utils.validate_enrollment_webhook",
    return_value=False,
)
@TASK_PATCH
def test_skips_when_the_webhook_is_not_configured(
    mock_task,
    _mock_validate,  # noqa: PT019
):
    """Nothing is attempted on an install that does not use the webhook."""
    handle_role_assignment_created(None, role_assignment=_event())

    mock_task.delay.assert_not_called()
