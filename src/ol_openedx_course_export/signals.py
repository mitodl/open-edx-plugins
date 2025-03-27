"""
Signal handlers for the ol_openedx_course_export app.

This module implements a workaround for a compatibility issue between django-user-tasks
and Celery's protocol version 2. The create_user_task signal handler expects protocol
version 1 format but receives version 2, causing TypeError exceptions in the logs.

This fix wraps the original handler, converts protocol v2 messages to v1 format, and
ensures UserTask-based tasks work properly without generating errors.
"""

from celery import chain, signals
from cms.celery import APP
from user_tasks.signals import create_user_task

signals.before_task_publish.disconnect(create_user_task)


def create_user_task_wrapper(sender=None, body=None, **kwargs):
    return create_user_task(
        sender,
        body
        if APP.conf.task_protocol == 1
        else proto2_to_proto1(body, kwargs.get("headers", {})),
    )


signals.before_task_publish.connect(create_user_task_wrapper)


def proto2_to_proto1(body, headers):
    args, kwargs, embed = body
    embedded = _extract_proto2_embed(**embed)
    chained = embedded.pop("chain")
    new_body = dict(
        _extract_proto2_headers(**headers), args=args, kwargs=kwargs, **embedded
    )
    if chained:
        new_body["callbacks"].append(chain(chained))
    return new_body


def _extract_proto2_headers(  # noqa: PLR0913
    task_id, retries, eta, expires, group, timelimit, task, **_
):
    return {
        "id": task_id,
        "task": task,
        "retries": retries,
        "eta": eta,
        "expires": expires,
        "utc": True,
        "taskset": group,
        "timelimit": timelimit,
    }


def _extract_proto2_embed(callbacks, errbacks, chain, chord, **_):
    return {
        "callbacks": callbacks or [],
        "errbacks": errbacks,
        "chain": chain,
        "chord": chord,
    }
