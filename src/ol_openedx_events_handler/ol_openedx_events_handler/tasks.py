"""Celery tasks for the OL Open edX events handler plugin."""

import logging

import requests
from celery import shared_task
from django.conf import settings

log = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30


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

    headers = {
        "Content-Type": "application/json",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    log.info(
        "Sending course access role enrollment webhook for "
        "user '%s' in course '%s' (role: %s)",
        user_email,
        course_key,
        role,
    )

    response = requests.post(
        webhook_url,
        json=payload,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    log.info(
        "Successfully sent enrollment webhook for user '%s' in course '%s'. "
        "Response status: %s",
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

    headers = {
        "Content-Type": "application/json",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    log.info(
        "Sending certificate webhook for user '%s' in course '%s'.",
        user_email,
        course_key,
    )
    response = requests.post(
        webhook_url,
        json=payload,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    log.info(
        "Successfully sent certificate webhook for user '%s' in course '%s'. "
        "Response status: %s",
        user_email,
        course_key,
        response.status_code,
    )
