"""Rapid-response functionality"""

import logging
from datetime import datetime
from functools import wraps

import pkg_resources
import pytz
from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.template import Context, Template
from django.utils.translation import gettext_lazy as _
from web_fragments.fragment import Fragment
from webob.response import Response
from xblock.core import XBlock, XBlockAside
from xblock.fields import Boolean, Scope
from xmodule.modulestore.django import modulestore

from rapid_response_xblock.models import (
    RapidResponseRun,
    RapidResponseSubmission,
)

log = logging.getLogger(__name__)


def get_resource_bytes(path):
    """
    Helper method to get the unicode contents of a resource in this repo.

    Args:
        path (str): The path of the resource

    Returns:
        unicode: The unicode contents of the resource at the given path
    """  # noqa: D401
    resource_contents = pkg_resources.resource_string(__name__, path)
    return resource_contents.decode("utf-8")


def render_template(template_path, context=None):
    """
    Evaluate a template by resource path, applying the provided context.
    """
    context = context or {}
    template_str = get_resource_bytes(template_path)
    template = Template(template_str)
    return template.render(Context(context))


def staff_only(handler_method):
    """
    Wrapper that ensures a handler method is enabled for staff users only
    """  # noqa: D401

    @wraps(handler_method)
    def wrapper(aside_instance, *args, **kwargs):
        if not aside_instance.is_staff():
            return Response(status=403, json_body="Unauthorized (staff only)")
        return handler_method(aside_instance, *args, **kwargs)

    return wrapper


BLOCK_PROBLEM_CATEGORY = "problem"
MULTIPLE_CHOICE_TYPE = "multiplechoiceresponse"


class RapidResponseAside(XBlockAside):
    """
    XBlock aside that enables rapid-response functionality for an XBlock
    """

    enabled = Boolean(
        display_name=_("Rapid response enabled status"),
        default=False,
        scope=Scope.settings,
        help=_("Indicates whether or not a problem is enabled for rapid response"),
    )

    @XBlockAside.aside_for("student_view")
    def student_view_aside(self, block, context=None):  # noqa: ARG002
        """
        Renders the aside contents for the student view
        """  # noqa: D401
        fragment = Fragment("")
        if not self.is_staff() or not self.enabled:
            return fragment
        fragment.add_content(
            render_template("static/html/rapid.html", {"is_open": self.has_open_run})
        )
        fragment.add_css(get_resource_bytes("static/css/rapid.css"))
        fragment.add_javascript(get_resource_bytes("static/js/src_js/rapid.js"))
        fragment.add_javascript(get_resource_bytes("static/js/lib/d3.v4.min.js"))
        fragment.initialize_js("RapidResponseAsideInit")
        return fragment

    @XBlockAside.aside_for("author_view")
    def author_view_aside(self, block, context=None):  # noqa: ARG002
        """
        Renders the aside contents for the author view
        """  # noqa: D401
        if settings.ENABLE_RAPID_RESPONSE_AUTHOR_VIEW:
            return self.get_studio_fragment()
        return Fragment("")

    @XBlockAside.aside_for("studio_view")
    def studio_view_aside(self, block, context=None):  # noqa: ARG002
        """
        Renders the aside contents for the studio view
        """  # noqa: D401
        return self.get_studio_fragment()

    @XBlock.handler
    @staff_only
    def toggle_block_open_status(self, request=None, suffix=None):  # noqa: ARG002
        """
        Toggles the open/closed status for the rapid-response-enabled block
        """
        with transaction.atomic():
            run = RapidResponseRun.objects.filter(
                problem_usage_key=self.wrapped_block_usage_key,
                course_key=self.course_key,
            ).first()

            if run and run.open:
                run.open = False
                run.save()
            else:
                run = RapidResponseRun.objects.create(
                    problem_usage_key=self.wrapped_block_usage_key,
                    course_key=self.course_key,
                    open=True,
                )
        return Response(
            json_body={
                "is_open": run.open,
            }
        )

    @XBlock.handler
    def toggle_block_enabled(self, request=None, suffix=None):  # noqa: ARG002
        """
        Toggles the enabled status for the rapid-response-enabled block
        """
        self.enabled = not self.enabled
        return Response(json_body={"is_enabled": self.enabled})

    @XBlock.handler
    @staff_only
    def responses(self, request=None, suffix=None):  # noqa: ARG002
        """
        Returns student responses for rapid-response-enabled block
        """  # noqa: D401
        run_querysets = RapidResponseRun.objects.filter(
            problem_usage_key=self.wrapped_block_usage_key,
            course_key=self.course_key,
        )
        runs = self.serialize_runs(run_querysets)
        # Only the most recent run should possibly be open
        # If other runs are marked open due to some race condition, look at only the
        # first
        is_open = runs[0]["open"] if runs else False
        choices = self.choices
        counts = self.get_counts_for_problem(
            [run["id"] for run in runs],
            choices,
        )

        total_counts = {
            run["id"]: sum(counts[choice["answer_id"]][run["id"]] for choice in choices)
            for run in runs
        }

        return Response(
            json_body={
                "is_open": is_open,
                "runs": runs,
                "choices": choices,
                "counts": counts,
                "total_counts": total_counts,
                "server_now": datetime.now(tz=pytz.utc).isoformat(),
            }
        )

    @classmethod
    def should_apply_to_block(cls, block):
        """
        Overrides base XBlockAside implementation. Indicates whether or not this aside
        should apply to a given block.

        Due to the different ways that the Studio and LMS runtimes construct XBlock
        instances, the problem type of the given block needs to be retrieved in
        different ways.
        """  # noqa: D401
        if getattr(block, "category", None) != BLOCK_PROBLEM_CATEGORY:
            return False
        block_problem_types = None
        # LMS passes in the block instance with `problem_types` as a property of
        # `descriptor`
        if hasattr(block, "descriptor"):
            block_problem_types = getattr(block.descriptor, "problem_types", None)
        # Studio passes in the block instance with `problem_types` as a top-level property  # noqa: E501
        elif hasattr(block, "problem_types"):
            block_problem_types = block.problem_types
        # We only want this aside to apply to the block if the problem is multiple
        # choice AND there are not multiple problem types.
        return block_problem_types == {MULTIPLE_CHOICE_TYPE}

    def get_studio_fragment(self):
        """
        Generate a Studio view based aside fragment. (Used in Studio View and Author
          View)
        """
        fragment = Fragment("")
        fragment.add_content(
            render_template(
                "static/html/rapid_studio.html", {"is_enabled": self.enabled}
            )
        )
        fragment.add_css(get_resource_bytes("static/css/rapid.css"))
        fragment.add_javascript(get_resource_bytes("static/js/src_js/rapid_studio.js"))
        fragment.initialize_js("RapidResponseAsideStudioInit")
        return fragment

    @property
    def wrapped_block_usage_key(self):
        """The usage_key for the block that is being wrapped by this aside"""
        return self.scope_ids.usage_id.usage_key

    @property
    def course_key(self):
        """The course_key for this aside"""
        return self.scope_ids.usage_id.course_key

    def is_staff(self):
        """Returns True if the user has staff permissions"""  # noqa: D401
        return getattr(self.runtime, "user_is_staff", False)

    @property
    def has_open_run(self):
        """
        Check if there is an open run for this problem
        """
        run = (
            RapidResponseRun.objects.filter(
                problem_usage_key=self.wrapped_block_usage_key,
                course_key=self.course_key,
            )
            .order_by("-created")
            .first()
        )
        return run and run.open

    @property
    def choices(self):
        """
        Look up choices from the problem XML

        Returns:
            list of dict: A list of answer id/answer text dicts, in the order the
            choices are listed in the XML
        """
        problem = modulestore().get_item(self.wrapped_block_usage_key)
        tree = problem.lcp.tree
        choice_elements = tree.xpath("//choicegroup/choice")
        return [
            {
                "answer_id": choice.get("name"),
                "answer_text": (
                    next(iter(choice.itertext())) if list(choice.itertext()) else ""
                ),
            }
            for choice in choice_elements
        ]

    @staticmethod
    def serialize_runs(runs):
        """
        Look up rapid response runs for a problem and return a serialized representation

        Args:
            runs (iterable of RapidResponseRun): A queryset of RapidResponseRun

        Returns:
            list of dict: a list of serialized runs
        """
        return [
            {
                "id": run.id,
                "created": run.created.isoformat(),
                "open": run.open,
            }
            for run in runs
        ]

    @staticmethod
    def get_counts_for_problem(run_ids, choices):
        """
        Produce histogram count data for a given problem

        Args:
            run_ids (list of int): Serialized run id for the problem
            choices (list of dict): Serialized choices

        Returns:
            dict:
                A mapping of answer id => run id => count for that run
        """
        response_data = (
            RapidResponseSubmission.objects.filter(run__id__in=run_ids)
            .values("answer_id", "run")
            .annotate(count=Count("answer_id"))
        )
        # Make sure every answer has a count and convert to JSON serializable format
        response_counts = {
            (item["answer_id"], item["run"]): item["count"] for item in response_data
        }

        return {
            choice["answer_id"]: {
                run_id: response_counts.get((choice["answer_id"], run_id), 0)
                for run_id in run_ids
            }
            for choice in choices
        }
