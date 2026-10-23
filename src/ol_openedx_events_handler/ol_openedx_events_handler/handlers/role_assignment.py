"""Signal handler for openedx-authz role assignments."""

import logging

from django.conf import settings

log = logging.getLogger(__name__)


def _external_key(namespaced_key, namespace, separator):
    """
    Return the value half of a namespaced key, if it carries this namespace.

    The namespace is compared rather than stripped. A subject under any
    namespace other than ``user^`` is not a single learner, and stripping
    whatever prefix happens to be there would turn its name into a username --
    one that may well belong to somebody, who would then be mirrored onto the
    course team. The same applies to a role key that is not ``role^``.

    Returns None when the namespace does not match, which also covers a key
    carrying no namespace at all.
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
    this plugin inferring it from the key. The type has to match exactly:
    ``CCXCourseOverviewData`` subclasses ``CourseOverviewData``, so an
    ``isinstance`` test would let a CCX locator through to a consumer that
    records ordinary course runs.

    Library and organization scopes resolve to other subclasses, and the
    wizard's "all courses in this organization" and "all courses on the
    platform" options to glob subclasses. None of them name a single run for
    the consumer to key a record on, so none are mirrored. The glob ones are
    logged a level up, because a grant made that way looks like it worked.
    """
    from opaque_keys import InvalidKeyError  # noqa: PLC0415
    from openedx_authz.api.data import CourseOverviewData, ScopeData  # noqa: PLC0415

    try:
        scope = ScopeData(namespaced_key=scope_key)
        if type(scope) is not CourseOverviewData:
            # A course-namespaced scope that is not one course is a glob: the
            # operator asked for a whole org or the platform and got nothing.
            level = (
                log.info
                if scope.NAMESPACE == CourseOverviewData.NAMESPACE
                else log.debug
            )
            level(
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

    Subjects under another namespace fall out here, on the namespace rather
    than on the lookup failing -- see ``_external_key`` for why that matters.
    """
    from django.contrib.auth import get_user_model  # noqa: PLC0415
    from openedx_authz.api.data import UserData  # noqa: PLC0415

    username = _external_key(subject_key, UserData.NAMESPACE, UserData.SEPARATOR)
    if not username:
        log.info(
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
