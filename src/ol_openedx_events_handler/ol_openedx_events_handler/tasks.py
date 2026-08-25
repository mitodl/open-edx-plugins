"""Celery tasks for the OL Open edX events handler plugin."""

import logging

import requests
from celery import shared_task
from django.conf import settings

log = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30

HTTP_BAD_REQUEST = 400
HTTP_REQUEST_TIMEOUT = 408
HTTP_TOO_MANY_REQUESTS = 429
HTTP_SERVER_ERROR = 500

# 4xx responses that describe a transient condition rather than a bad request,
# so they are retried like a 5xx instead of being dropped.
RETRYABLE_CLIENT_ERRORS = frozenset({HTTP_REQUEST_TIMEOUT, HTTP_TOO_MANY_REQUESTS})


def _post_webhook(webhook_url, access_token, payload):
    """
    Send a webhook payload and return the response.

    Shared by the webhook tasks so the auth header, content type and timeout
    are applied the same way for every webhook this plugin sends.

    Args:
        webhook_url (str): The endpoint to POST to.
        access_token (str): Bearer token, or None to send no auth header.
        payload (dict): The JSON body to send.

    Returns:
        requests.Response: The raw response, for the caller to interpret.
    """
    headers = {"Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    return requests.post(
        webhook_url,
        json=payload,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )


@shared_task(
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 2},
    retry_backoff=True,
    retry_backoff_max=120,
)
def notify_course_access_role_addition(user_email, course_key, role):
    """
    Notify an external system that a user has been given a course access role.

    Sends a POST request to the configured webhook endpoint so the
    external system can decide on whatever it wants to do with this event.

    Args:
        user_email (str): The email address of the user.
        course_key (str): The string representation of the course key.
        role (str): The course access role assigned to the user.
    """
    webhook_url = getattr(settings, "ENROLLMENT_WEBHOOK_URL", None)
    access_token = getattr(settings, "ENROLLMENT_WEBHOOK_ACCESS_TOKEN", None)

    payload = {
        "email": user_email,
        "course_id": course_key,
        "role": role,
    }

    log.info(
        "Sending course access role enrollment webhook for "
        "user '%s' in course '%s' (role: %s)",
        user_email,
        course_key,
        role,
    )

    response = _post_webhook(webhook_url, access_token, payload)
    response.raise_for_status()

    log.info(
        "Successfully sent enrollment webhook for user '%s' in course '%s'. "
        "Response status: %s",
        user_email,
        course_key,
        response.status_code,
    )


@shared_task(
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 2},
    retry_backoff=True,
    retry_backoff_max=120,
)
def notify_course_enrollment_created(user_email, course_key, mode):
    """
    Notify an external system that a user has been enrolled in a course.

    Sends a POST request to the configured webhook endpoint so the external
    system can mirror the enrollment.

    A 4xx response is logged and not retried: it means the request will never
    succeed as-is (e.g. the learner or the course run does not exist in the
    external system, or the access token is invalid). The exceptions are the
    transient client errors in ``RETRYABLE_CLIENT_ERRORS``, which are retried
    like a 5xx.

    Args:
        user_email (str): The email address of the enrolled user.
        course_key (str): The string representation of the course key.
        mode (str): The enrollment mode, e.g. 'audit' or 'verified'.
    """
    webhook_url = getattr(settings, "ENROLLMENT_WEBHOOK_URL", None)
    access_token = getattr(settings, "ENROLLMENT_WEBHOOK_ACCESS_TOKEN", None)

    payload = {
        "email": user_email,
        "course_id": course_key,
        "mode": mode,
    }

    log.info(
        "Sending enrollment webhook for user '%s' in course '%s' (mode: %s)",
        user_email,
        course_key,
        mode,
    )

    response = _post_webhook(webhook_url, access_token, payload)

    is_client_error = HTTP_BAD_REQUEST <= response.status_code < HTTP_SERVER_ERROR
    if is_client_error and response.status_code not in RETRYABLE_CLIENT_ERRORS:
        log.error(
            "Enrollment webhook rejected for user '%s' in course '%s'. "
            "Response status: %s, body: %s. Not retrying, because the request "
            "cannot succeed unchanged; this enrollment stays unmirrored until "
            "the external system reconciles it.",
            user_email,
            course_key,
            response.status_code,
            response.text,
        )
        return

    response.raise_for_status()

    log.info(
        "Enrollment mirrored for user '%s' in course '%s'. Response status: %s",
        user_email,
        course_key,
        response.status_code,
    )


def _get_certificate_webhook_url():
    """Return the configured certificate webhook URL."""
    return getattr(settings, "CERTIFICATE_WEBHOOK_URL", None)


def _get_certificate_webhook_access_token():
    """Return the configured certificate webhook access token."""
    return getattr(settings, "CERTIFICATE_WEBHOOK_ACCESS_TOKEN", None)


@shared_task(
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 2},
    retry_backoff=True,
    retry_backoff_max=120,
)
def create_certificate_for_passing_grade(user_email, course_key):
    """
    Notify an external system that a learner passed a course.

    Sends a POST request to the configured certificate webhook endpoint so the
    external system can create a certificate for the learner.
    """
    webhook_url = _get_certificate_webhook_url()
    access_token = _get_certificate_webhook_access_token()

    if not webhook_url or not access_token:
        log.error(
            "Certificate webhook is not fully configured. "
            "Skipping dispatch for user '%s' in course '%s'.",
            user_email,
            course_key,
        )
        return

    payload = {
        "email": user_email,
        "course_id": course_key,
    }

    log.info(
        "Sending certificate webhook for user '%s' in course '%s'.",
        user_email,
        course_key,
    )
    response = _post_webhook(webhook_url, access_token, payload)
    response.raise_for_status()

    log.info(
        "Successfully sent certificate webhook for user '%s' in course '%s'. "
        "Response status: %s",
        user_email,
        course_key,
        response.status_code,
    )
