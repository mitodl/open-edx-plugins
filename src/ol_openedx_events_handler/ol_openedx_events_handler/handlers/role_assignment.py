"""Signal handler for openedx-authz role assignments."""

import logging

from django.conf import settings

log = logging.getLogger(__name__)


def _external_key(namespaced_key, separator):
    """
    Return the value half of a namespaced key such as ``user^jdoe``.

    Returns None when the key carries no namespace, which would mean
    openedx-authz changed the format rather than that this particular
    assignment is uninteresting -- worth noticing rather than guessing at.
    """
    if not namespaced_key or separator not in namespaced_key:
        return None
    return namespaced_key.split(separator, 1)[1]


def _course_key_from_scope(scope_key):
    """
    Return the course this assignment is scoped to, or None if it is not one.

    Parsing the scope as a course key is the test, rather than matching on the
    namespace: the namespace carries the course key's own version prefix, so
    matching it would quietly stop working on the next course key version.
    Library and organization scopes land here and are not mirrored, because
    the consumer keys its records on a single course run.
    """
    from opaque_keys import InvalidKeyError  # noqa: PLC0415
    from opaque_keys.edx.keys import CourseKey  # noqa: PLC0415
    from openedx_authz.api.data import ScopeData  # noqa: PLC0415

    scope = _external_key(scope_key, ScopeData.SEPARATOR)
    if not scope:
        log.warning(
            "Role assignment carried an unparseable scope %r. Skipping.",
            scope_key,
        )
        return None
    try:
        return CourseKey.from_string(scope)
    except InvalidKeyError:
        log.debug("Ignoring role assignment in scope '%s' - not a course.", scope)
        return None


def _legacy_role_for(role_key, course_key):
    """
    Translate an authz role name into the course access role name, or None.

    The consumer and ``ENROLLMENT_COURSE_ACCESS_ROLES`` both speak the legacy
    names, so an operator configuring this does not have to know openedx-authz's
    vocabulary. Roles with no legacy equivalent are not mirrored.
    """
    from common.djangoapps.student.roles import (  # noqa: PLC0415
        get_legacy_role_from_authz_role,
    )
    from openedx_authz.api.data import RoleData  # noqa: PLC0415

    authz_role = _external_key(role_key, RoleData.SEPARATOR)
    legacy_role = get_legacy_role_from_authz_role(authz_role) if authz_role else None
    if not legacy_role:
        log.debug(
            "Ignoring role assignment %r in course '%s' - it has no equivalent "
            "course access role.",
            role_key,
            course_key,
        )
        return None

    allowed_roles = getattr(settings, "ENROLLMENT_COURSE_ACCESS_ROLES", [])
    if legacy_role not in allowed_roles:
        log.info(
            "Ignoring role '%s' in course %s - not in allowed roles %s",
            legacy_role,
            course_key,
            allowed_roles,
        )
        return None
    return legacy_role


def _email_for_subject(subject_key, course_key):
    """
    Return the email of the user this assignment is for, or None.

    openedx-authz can also assign a role to a group, which arrives with a
    different namespace and no single learner for the consumer to record.
    Those fall out here.
    """
    from django.contrib.auth import get_user_model  # noqa: PLC0415
    from openedx_authz.api.data import UserData  # noqa: PLC0415

    username = _external_key(subject_key, UserData.SEPARATOR)
    if not username:
        log.warning(
            "Role assignment carried an unparseable subject %r for course '%s'. "
            "Skipping.",
            subject_key,
            course_key,
        )
        return None

    user_model = get_user_model()
    try:
        email = user_model.objects.values_list("email", flat=True).get(
            username=username
        )
    except user_model.DoesNotExist:
        log.warning(
            "Cannot resolve a user for '%s'. Skipping enrollment webhook for "
            "course '%s'. A group assignment lands here too; only user "
            "assignments are mirrored.",
            username,
            course_key,
        )
        return None

    if not email:
        log.warning(
            "User '%s' has no email. Skipping enrollment webhook for course '%s'.",
            username,
            course_key,
        )
        return None
    return email


def handle_role_assignment_created(
    sender,  # noqa: ARG001
    role_assignment,
    **kwargs,  # noqa: ARG001
):
    """
    Handle ROLE_ASSIGNMENT_CREATED from openedx-authz.

    Course team roles are moving out of ``CourseAccessRole`` and into
    openedx-authz. A grant made through edx-platform's own role classes emits
    ``COURSE_ACCESS_ROLE_ADDED`` as well, so the other receiver already covers
    the instructor dashboard and Studio's course team page. The Admin Console
    assigns through openedx-authz directly, and that path emits only this
    event -- so without this receiver a course team member added there is never
    mirrored, and the consumer never learns they are on the course team.

    A grant that emits both events sends the webhook twice. That is deliberate:
    the consumer records the role with get_or_create, so a duplicate is a
    wasted request rather than a wrong one, and missing a role outright is the
    worse failure.

    Args:
        sender: The sender of the signal.
        role_assignment (RoleAssignmentData): operation, subject, role and
            scope, each a namespaced key such as ``role^course_staff``.
        **kwargs: Additional keyword arguments from the signal.
    """
    from ol_openedx_events_handler.tasks import (  # noqa: PLC0415
        notify_course_access_role_addition,
    )
    from ol_openedx_events_handler.utils import (  # noqa: PLC0415
        validate_enrollment_webhook,
    )

    if not validate_enrollment_webhook():
        return

    course_key = _course_key_from_scope(role_assignment.scope)
    if not course_key:
        return

    legacy_role = _legacy_role_for(role_assignment.role, course_key)
    if not legacy_role:
        return

    user_email = _email_for_subject(role_assignment.subject, course_key)
    if not user_email:
        return

    log.info(
        "AuthZ role %r (%s) assigned to user '%s' in course '%s'. "
        "Dispatching enrollment webhook.",
        role_assignment.role,
        legacy_role,
        user_email,
        course_key,
    )

    notify_course_access_role_addition.delay(
        user_email=user_email,
        course_key=str(course_key),
        role=legacy_role,
    )
