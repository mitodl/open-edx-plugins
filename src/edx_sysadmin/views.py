"""
Views for the Open edX SysAdmin Plugin
"""

# pylint: disable=wrong-import-order
import logging
from io import StringIO

from common.djangoapps.student.roles import CourseInstructorRole
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.html import escape
from django.utils.translation import gettext as _
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import condition
from django.views.generic.base import RedirectView, TemplateView
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.django import modulestore

from edx_sysadmin import git_import
from edx_sysadmin.forms import UserRegistrationForm
from edx_sysadmin.git_import import GitImportError
from edx_sysadmin.models import CourseGitLog
from edx_sysadmin.utils.markup import HTML, Text
from edx_sysadmin.utils.utils import (
    create_user_account,
    get_course_by_id,
    get_registration_required_extra_fields_with_values,
    is_registration_api_functional,
    user_has_access_to_courses_panel,
    user_has_access_to_git_import_panel,
    user_has_access_to_git_logs_panel,
    user_has_access_to_sysadmin,
    user_has_access_to_users_panel,
)

log = logging.getLogger(__name__)


@method_decorator(
    user_passes_test(
        user_has_access_to_sysadmin, login_url="/404", redirect_field_name=None
    ),
    name="dispatch",
)
class SysadminDashboardRedirectionView(RedirectView):
    """Redirection view to land user to specific panel"""

    def get_redirect_url(self, *args, **kwargs):  # noqa: ARG002
        """Override redirection_url"""

        if user_has_access_to_users_panel(self.request.user):
            return reverse("sysadmin:users")
        elif user_has_access_to_courses_panel(self.request.user):
            return reverse("sysadmin:courses")
        elif user_has_access_to_git_logs_panel(self.request.user):
            return reverse("sysadmin:gitlogs")
        elif user_has_access_to_git_import_panel(self.request.user):
            return reverse("sysadmin:gitimport")
        else:
            raise Http404


@method_decorator(ensure_csrf_cookie, name="dispatch")
@method_decorator(
    user_passes_test(
        user_has_access_to_sysadmin, login_url="/404", redirect_field_name=None
    ),
    name="dispatch",
)
@method_decorator(
    cache_control(no_cache=True, no_store=True, must_revalidate=True), name="dispatch"
)
@method_decorator(condition(etag_func=None), name="dispatch")
class SysadminDashboardBaseView(TemplateView):
    """Base view for SysAdmin Dashboard's Panels."""

    template_name = "edx_sysadmin/base.html"

    def get_context_data(self, **kwargs):
        """
        Override get_context_data method to add custom fields
        """
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "show_users_tab": user_has_access_to_users_panel(self.request.user),
                "show_courses_tab": user_has_access_to_courses_panel(self.request.user),
                "show_git_logs_tab": user_has_access_to_git_logs_panel(
                    self.request.user
                ),
                "show_git_import_tab": user_has_access_to_git_import_panel(
                    self.request.user
                ),
            }
        )
        return context


@method_decorator(
    user_passes_test(
        user_has_access_to_courses_panel, login_url="/404", redirect_field_name=None
    ),
    name="dispatch",
)
class CoursesPanel(SysadminDashboardBaseView):
    """
    This manages deleting courses.
    """

    template_name = "edx_sysadmin/courses.html"
    datatable = []  # type: ignore  # noqa: PGH003

    def get_course_summaries(self):
        """Get an iterable list of course summaries."""

        return modulestore().get_course_summaries()

    def make_datatable(self, courses=None):
        """Create course information datatable"""

        data = {}
        for course in courses or self.get_course_summaries():
            data[course.id] = {
                "display_name": course.display_name,
                "course_id": course.id,
                "git_directory": course.id.course,
            }

        return {
            "header": [
                _("Course Name"),
                _("Directory/ID"),
                # Translators: "Git Commit" is a computer command; see http://gitref.org/basic/#commit
                _("Git Commit"),
                _("Last Change"),
                _("Last Editor"),
                _("Action"),
            ],
            "title": _("Information about all courses"),
            "data": data,
            "api_url": reverse("sysadmin:api:git-course-details"),
        }

    def get_context_data(self, **kwargs):
        """
        Override get_context_data method to add custom fields
        """
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "is_courses_tab": True,
                "datatable": self.make_datatable(),
            }
        )
        return context

    def post(self, request):
        """Handle delete action from courses view"""

        action = request.POST.get("action", "")
        message = ""
        if action == "del_course":
            course_id = request.POST.get("course_id", "").strip()
            course_key = CourseKey.from_string(course_id)
            course_found = False
            try:
                course = get_course_by_id(course_key)
                course_found = True
            except Exception as err:  # noqa: BLE001
                message += Text(
                    _(
                        "{div_start} Error - cannot get course with ID {course_key} {error} {div_end}"  # noqa: E501
                    )
                ).format(
                    div_start=HTML("<div class='error'>"),
                    course_key=course_key,
                    error=HTML("<br/><pre>{error}</pre>").format(
                        error=escape(str(err))
                    ),
                    div_end=HTML("</div>"),
                )

            if course_found:
                # delete course that is stored with mongodb backend
                modulestore().delete_course(course.id, request.user.id)
                # don't delete user permission groups, though
                message += Text(
                    _(
                        "{font_start} Deleted {course_name} = {course_id} {location} {font_end}"  # noqa: E501
                    )
                ).format(
                    font_start=HTML("<font class='success'>"),
                    location=course.location,
                    course_id=course.id,
                    course_name=course.display_name,
                    font_end=HTML("</font>"),
                )

        context = self.get_context_data()
        context.update({"msg": message})
        return render(request, self.template_name, context)


@method_decorator(
    user_passes_test(
        user_has_access_to_users_panel, login_url="/404", redirect_field_name=None
    ),
    name="dispatch",
)
class UsersPanel(SysadminDashboardBaseView):
    """View to show the User Panel of SysAdmin."""

    template_name = "edx_sysadmin/users.html"

    def get_context_data(self, **kwargs):
        """
        Override get_context_data method to add custom fields
        """
        context = super().get_context_data(**kwargs)
        initial_data = kwargs.pop("initial_data", None)
        extra_fields = get_registration_required_extra_fields_with_values()

        if not is_registration_api_functional():
            context["disclaimer"] = True

        context.update(
            {
                "user_registration_form": UserRegistrationForm(
                    initial_data, extra_fields=extra_fields
                ),
                "is_users_tab": True,
            }
        )
        return context

    def post(self, request, *args, **kwargs):  # noqa: ARG002
        """
        POST method for User registration
        """
        extra_fields = get_registration_required_extra_fields_with_values()
        form = UserRegistrationForm(request.POST, extra_fields=extra_fields)
        context = self.get_context_data(initial_data=request.POST, **kwargs)
        if form.is_valid():
            context.update(
                create_user_account(form.cleaned_data, request.build_absolute_uri)
            )
            if context.get("success_message"):
                success_message = context.get("success_message")
                context = self.get_context_data()
                context["success_message"] = success_message
        else:
            context["error_message"] = _(
                "Unable to create new account due to invalid data"
            )

        return render(request, self.template_name, context)


@method_decorator(
    user_passes_test(
        user_has_access_to_git_import_panel, login_url="/404", redirect_field_name=None
    ),
    name="dispatch",
)
class GitImport(SysadminDashboardBaseView):
    """
    This provide the view to load or update courses from github
    """

    template_name = "edx_sysadmin/gitimport.html"

    def get_context_data(self, **kwargs):
        """
        Override get_context_data method to add custom fields
        """
        context = super().get_context_data(**kwargs)
        context["is_git_import_tab"] = True
        return context

    def get_course_from_git(self, gitloc, branch):
        """Download and run the checks for importing a course in git"""

        if not (
            gitloc.endswith(".git") or gitloc.startswith(("http:", "https:", "git:"))
        ):
            return HTML("<p style='color:#cb0712'>{0}</p>").format(
                "The git repo location should end with '.git', and be a valid url"
            )

        return self.import_mongo_course(gitloc, branch)

    def import_mongo_course(self, gitloc, branch):
        """
        Import course using management command and captures logging output
        at debug level for display in template
        """

        message = ""

        log.debug("Adding course using git repo %s", gitloc)

        # Grab logging output for debugging imports
        output = StringIO()
        import_log_handler = logging.StreamHandler(output)
        import_log_handler.setLevel(logging.DEBUG)

        logger_names = [
            "xmodule.modulestore.xml_importer",
            "edx_sysadmin.git_import",
            "xmodule.modulestore.xml",
            "xmodule.seq_module",
        ]
        loggers = []

        for logger_name in logger_names:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.DEBUG)
            logger.addHandler(import_log_handler)
            loggers.append(logger)

        error_msg = ""
        try:
            git_import.add_repo(gitloc, None, branch)
        except GitImportError as ex:
            error_msg = str(ex)
        ret = output.getvalue()

        # Remove handler hijacks
        for logger in loggers:
            logger.setLevel(logging.NOTSET)
            logger.removeHandler(import_log_handler)

        if error_msg:
            msg_header = error_msg
            color = "#cb0712"
        else:
            msg_header = _("Added Course")
            color = "#008000"

        message = HTML("<h4 style='color:{0}'>{1}</h4>").format(color, msg_header)
        message += HTML("<pre>{0}</pre>").format(escape(ret))
        return message

    def post(self, request):
        """Handle all actions from courses view"""

        message = ""
        action = request.POST.get("action", "")

        if action == "add_course":
            gitloc = (
                request.POST.get("repo_location", "")
                .strip()
                .replace(" ", "")
                .replace(";", "")
            )
            branch = (
                request.POST.get("repo_branch", "")
                .strip()
                .replace(" ", "")
                .replace(";", "")
            )
            message += self.get_course_from_git(gitloc, branch)

        context = self.get_context_data()
        context.update({"msg": message})
        return render(request, self.template_name, context)


@method_decorator(
    user_passes_test(
        user_has_access_to_git_logs_panel, login_url="/404", redirect_field_name=None
    ),
    name="dispatch",
)
class GitLogs(SysadminDashboardBaseView):
    """
    This provides a view into the import of courses from git repositories.
    It is convenient for allowing course teams to see what may be wrong with
    their xml
    """

    template_name = "edx_sysadmin/gitlogs.html"

    def get_context_data(self, **kwargs):
        """
        Override get_context_data method to add custom fields
        """
        context = super().get_context_data(**kwargs)
        context["is_git_logs_tab"] = True
        return context

    def get(self, request, *args, **kwargs):  # noqa: ARG002
        """Show logs of imports that happened as a result of a git import"""
        course_id = kwargs.get("course_id")
        if course_id:
            course_id = CourseKey.from_string(course_id)

        page_size = 10
        error_msg = ""

        if course_id is None:
            if not request.user.is_staff:
                user_courses = request.user.courseaccessrole_set.filter(
                    role=CourseInstructorRole.ROLE
                ).values_list("course_id", flat=True)
                cilset = CourseGitLog.objects.filter(
                    course_id__in=user_courses
                ).order_by("-created")
            else:
                cilset = CourseGitLog.objects.order_by("-created")
        else:
            # Allow only course-admin and staff users
            if not (
                request.user.is_staff
                or CourseInstructorRole(course_id).has_user(request.user)
            ):
                raise Http404
            log.debug("course_id=%s", course_id)
            cilset = CourseGitLog.objects.filter(course_id=course_id).order_by(
                "-created"
            )
            log.debug("cilset length=%s", len(cilset))

        # Paginate the query set
        paginator = Paginator(cilset, page_size)
        try:
            logs = paginator.page(request.GET.get("page"))
        except PageNotAnInteger:
            logs = paginator.page(1)
        except EmptyPage:
            # If the page is too high or low
            given_page = int(request.GET.get("page"))
            page = min(max(1, given_page), paginator.num_pages)
            logs = paginator.page(page)

        context = self.get_context_data(**kwargs)
        context.update(
            {
                "logs": logs,
                "course_id": course_id if course_id else None,
                "error_msg": error_msg,
                "page_size": page_size,
            }
        )

        return render(request, self.template_name, context)
