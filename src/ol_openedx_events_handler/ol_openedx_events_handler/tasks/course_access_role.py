"""Celery tasks for course staff webhook notifications."""

import logging

import requests
from celery import shared_task
from django.conf import settings

log = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30


@shared_task(
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
    retry_backoff_max=120,
)
def notify_course_access_role_addition(user_email, course_key, role):
    """
    Notify an external system that a user has been given a course staff role.

    Sends a POST request to the configured webhook endpoint so the
    external system can enroll the user as an auditor in the course.

    Args:
        user_email (str): The email address of the user.
        course_key (str): The string representation of the course key.
        role (str): The course access role assigned to the user.
    """
    webhook_url = getattr(settings, "ENROLLMENT_WEBHOOK_URL", None)
    webhook_key = getattr(settings, "ENROLLMENT_WEBHOOK_KEY", None)

    payload = {
        "email": user_email,
        "course_id": course_key,
        "role": role,
    }

    headers = {
        "Content-Type": "application/json",
    }
    if webhook_key:
        headers["Authorization"] = f"Bearer {webhook_key}"

    log.info(
        "Sending course staff enrollment webhook for "
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
