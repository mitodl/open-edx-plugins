"""Signal handler for openedx-authz role assignments."""

import logging

from django.conf import settings

log = logging.getLogger(__name__)


def _external_key(namespaced_key, namespace, separator):
    """
    Return the value half of a namespaced key, if it carries this namespace.

    The namespace is checked rather than stripped. openedx-authz can assign a
    role to something other than a user -- a group arrives as ``group^<name>``
    -- and stripping whatever prefix happens to be there would turn that into a
    username. A group whose name matches an existing user would then mirror a
    course team role onto that individual, so the prefix has to match.

    Returns None when it does not, which also covers a key carrying no
    namespace at all.
    """
    if not namespaced_key:
        return None
    head, found, value = namespaced_key.partition(separator)
    return value if found and head == namespace else None


def _course_key_from_scope(scope_key):
    """
    Return the course this assignment is scoped to, or None if it is not one.

    ``ScopeData`` resolves a namespaced key to the subclass for that scope
    type, so the library decides what counts as a single course rather than
    this plugin inferring it from the key. A library or organization scope
    comes back as another subclass, and the wizard's "all courses in this
    organization" and "all courses on the platform" options come back as glob
    subclasses -- none of which are ``CourseOverviewData``, and none of which
    the consumer can key a record on, since it records a single course run.
    """
    from opaque_keys import InvalidKeyError  # noqa: PLC0415
    from openedx_authz.api.data import CourseOverviewData, ScopeData  # noqa: PLC0415

    try:
        scope = ScopeData(namespaced_key=scope_key)
        if not isinstance(scope, CourseOverviewData):
            log.debug(
                "Ignoring role assignment in scope '%s' - not a single course.",
                scope_key,
            )
            return None
        # course_key is a cached_property, so a course namespace carrying a key
        # that does not parse raises on access rather than on construction --
        # it has to be read inside the try, not returned from the else block.
        course_key = scope.course_key
    except (TypeError, ValueError, InvalidKeyError):
        # TypeError covers a missing scope, which ScopeData regexes as a string.
        log.warning(
            "Role assignment carried an unparseable scope %r. Skipping.",
            scope_key,
        )
        return None
    return course_key


def _legacy_role_for(role_key, course_key):
    """
    Translate an authz role name into the course access role name, or None.

    The consumer and ``ENROLLMENT_COURSE_ACCESS_ROLES`` both speak the legacy
    names, so an operator configuring this does not have to know openedx-authz's
    vocabulary. Roles with no legacy equivalent are not mirrored, and neither is
    a key that does not carry the role namespace.
    """
    from openedx_authz.api.data import RoleData  # noqa: PLC0415
    from openedx_authz.constants.roles import (  # noqa: PLC0415
        LEGACY_COURSE_ROLE_EQUIVALENCES,
    )

    # openedx-authz owns the mapping and documents it as unique in both
    # directions so it can be read as a reverse lookup. Reading the constant
    # rather than calling edx-platform's get_legacy_role_from_authz_role keeps
    # the dependency on the package that emits the event.
    legacy_by_authz = {
        authz: legacy for legacy, authz in LEGACY_COURSE_ROLE_EQUIVALENCES.items()
    }
    authz_role = _external_key(role_key, RoleData.NAMESPACE, RoleData.SEPARATOR)
    legacy_role = legacy_by_authz.get(authz_role) if authz_role else None
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

    openedx-authz can also assign a role to a group, which arrives under a
    different namespace and has no single learner for the consumer to record.
    Those fall out here, on the namespace rather than on the lookup failing --
    a group named after an existing user would otherwise resolve to them.
    """
    from django.contrib.auth import get_user_model  # noqa: PLC0415
    from openedx_authz.api.data import UserData  # noqa: PLC0415

    username = _external_key(subject_key, UserData.NAMESPACE, UserData.SEPARATOR)
    if not username:
        log.debug(
            "Ignoring role assignment for subject %r in course '%s' - only "
            "assignments to a single user are mirrored.",
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
            "course '%s'.",
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

    ``role_assignment`` is a ``RoleAssignmentData``, whose subject, role and
    scope are each a namespaced key such as ``role^course_staff``.
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
