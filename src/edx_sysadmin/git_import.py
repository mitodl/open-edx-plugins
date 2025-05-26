"""
Provides a function for importing a git repository into the lms
instance when using a mongo modulestore
"""

# pylint: disable=wrong-import-order

import importlib
import logging
import os
import re
import subprocess
from io import StringIO

from celery import shared_task
from cms.djangoapps.contentstore.outlines import update_outline_from_modulestore
from django.conf import settings
from django.core import management
from django.core.management.base import CommandError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from opaque_keys.edx.locator import CourseLocator
from xmodule.modulestore.django import SignalHandler
from xmodule.util.sandboxing import DEFAULT_PYTHON_LIB_FILENAME

from edx_sysadmin.models import CourseGitLog
from edx_sysadmin.utils.utils import (
    DEFAULT_GIT_REPO_PREFIX,
    remove_old_course_import_logs,
)

log = logging.getLogger(__name__)

DEFAULT_GIT_REPO_DIR = "/openedx/course_repos"


# pylint: disable=raise-missing-from
class GitImportError(Exception):
    """
    Exception class for handling the typical errors in a git import.
    """

    MESSAGE = None

    def __init__(self, message=None):
        if message is None:
            message = self.MESSAGE
        super().__init__(message)


class GitImportNoDirError(GitImportError):
    """
    GitImportError when no directory exists at the specified path.
    """

    def __init__(self, repo_dir):
        super().__init__(
            _(
                "Path {0} doesn't exist, please create it, "
                "or configure a different path with "
                "GIT_REPO_DIR"
            ).format(repo_dir)
        )


class GitImportUrlBadError(GitImportError):
    """
    GitImportError when the git url provided wasn't usable.
    """

    MESSAGE = _(
        "Non usable git url provided. Expecting something like:"
        " git@github.com:edx/edx4edx_lite.git"
    )


class GitImportBadRepoError(GitImportError):
    """
    GitImportError when the cloned repository was malformed.
    """

    MESSAGE = _("Unable to get git log")


class GitImportCannotPullError(GitImportError):
    """
    GitImportError when the clone of the repository failed.
    """

    MESSAGE = _("git clone or pull failed!")


class GitImportXmlImportFailedError(GitImportError):
    """
    GitImportError when the course import command failed.
    """

    MESSAGE = _("Unable to run import command.")


class GitImportUnsupportedStoreError(GitImportError):
    """
    GitImportError when the modulestore doesn't support imports.
    """

    MESSAGE = _("The underlying module store does not support import.")


class GitImportRemoteBranchMissingError(GitImportError):
    """
    GitImportError when the remote branch doesn't exist.
    """

    # Translators: This is an error message when they ask for a
    # particular version of a git repository and that version isn't
    # available from the remote source they specified
    MESSAGE = _("The specified remote branch is not available.")


class GitImportCannotBranchError(GitImportError):
    """
    GitImportError when the local branch doesn't exist.
    """

    # Translators: Error message shown when they have asked for a git
    # repository branch, a specific version within a repository, that
    # doesn't exist, or there is a problem changing to it.
    MESSAGE = _("Unable to switch to specified branch. Please check your branch name.")


def cmd_log(cmd, cwd):
    """
    Helper function to redirect stderr to stdout and log the command
    used along with the output. Will raise subprocess.CalledProcessError if
    command doesn't return 0, and returns the command's output.
    """  # noqa: D401
    output = subprocess.check_output(  # noqa: S603
        cmd,
        cwd=cwd,
        stderr=subprocess.STDOUT,
    ).decode("utf-8")

    log.debug("Command was: %s. Working directory was: %s", " ".join(cmd), cwd)
    log.debug("Command output was: %r", output)
    return output


def switch_branch(branch, rdir):
    """
    Determine how to change the branch of the repo, and then
    use the appropriate git commands to do so.

    Raises an appropriate GitImportError exception if there is any issues with changing
    branches.
    """
    # Get the latest remote
    try:
        cmd_log(
            [
                "git",
                "fetch",
            ],
            rdir,
        )
    except subprocess.CalledProcessError as ex:
        log.exception("Unable to fetch remote: %r", ex.output)
        raise GitImportCannotBranchError  # noqa: B904

    # Check if the branch is available from the remote.
    cmd = [
        "git",
        "ls-remote",
        "origin",
        "-h",
        f"{DEFAULT_GIT_REPO_PREFIX}{branch}",
    ]
    try:
        output = cmd_log(cmd, rdir)
    except subprocess.CalledProcessError as ex:
        log.exception("Getting a list of remote branches failed: %r", ex.output)
        raise GitImportCannotBranchError  # noqa: B904
    if branch not in output:
        raise GitImportRemoteBranchMissingError
    # Check it the remote branch has already been made locally
    cmd = [
        "git",
        "branch",
        "-a",
    ]
    try:
        output = cmd_log(cmd, rdir)
    except subprocess.CalledProcessError as ex:
        log.exception("Getting a list of local branches failed: %r", ex.output)
        raise GitImportCannotBranchError  # noqa: B904
    branches = []
    for line in output.split("\n"):
        branches.append(line.replace("*", "").strip())  # noqa: PERF401

    if branch not in branches:
        # Checkout with -b since it is remote only
        cmd = [
            "git",
            "checkout",
            "--force",
            "--track",
            "-b",
            branch,
            f"origin/{branch}",
        ]
        try:
            cmd_log(cmd, rdir)
        except subprocess.CalledProcessError as ex:
            log.exception("Unable to checkout remote branch: %r", ex.output)
            raise GitImportCannotBranchError  # noqa: B904
    # Go ahead and reset hard to the newest version of the branch now that we know
    # it is local.
    try:
        cmd_log(
            [
                "git",
                "reset",
                "--hard",
                f"origin/{branch}",
            ],
            rdir,
        )
    except subprocess.CalledProcessError as ex:
        log.exception("Unable to reset to branch: %r", ex.output)
        raise GitImportCannotBranchError  # noqa: B904


@shared_task()
def add_repo(repo, rdir_in=None, branch=None):  # noqa: PLR0912, PLR0915, C901
    """
    Add a git repo into the mongo modulestore.
    If branch is left as None, it will fetch the most recent
    version of the current branch.
    """
    # pylint: disable=too-many-statements

    git_repo_dir = getattr(settings, "GIT_REPO_DIR", DEFAULT_GIT_REPO_DIR)
    git_import_static = getattr(settings, "GIT_IMPORT_STATIC", True)
    git_import_python_lib = getattr(settings, "GIT_IMPORT_PYTHON_LIB", True)
    python_lib_filename = getattr(
        settings, "PYTHON_LIB_FILENAME", DEFAULT_PYTHON_LIB_FILENAME
    )

    if not os.path.isdir(git_repo_dir):  # noqa: PTH112
        raise GitImportNoDirError(git_repo_dir)
    # pull from git
    if not (
        repo.endswith(".git") or repo.startswith(("http:", "https:", "git:", "file:"))
    ):
        raise GitImportUrlBadError

    if rdir_in:
        rdir = os.path.basename(rdir_in)  # noqa: PTH119
    else:
        rdir = repo.rsplit("/", 1)[-1].rsplit(".git", 1)[0]
    log.debug("rdir = %s", rdir)

    rdirp = f"{git_repo_dir}/{rdir}"
    if os.path.exists(rdirp):  # noqa: PTH110
        log.info("directory already exists, doing a git pull instead of git clone")
        cmd = [
            "git",
            "pull",
        ]
        cwd = rdirp
    else:
        cmd = [
            "git",
            "clone",
            repo,
        ]
        cwd = git_repo_dir

    cwd = os.path.abspath(cwd)  # noqa: PTH100
    try:
        ret_git = cmd_log(cmd, cwd=cwd)
    except subprocess.CalledProcessError as ex:
        log.exception("Error running git pull: %r", ex.output)
        raise GitImportCannotPullError  # noqa: B904

    if branch:
        switch_branch(branch, rdirp)

    # get commit id
    cmd = [
        "git",
        "log",
        "-1",
        "--format=%H",
    ]
    try:
        commit_id = cmd_log(cmd, cwd=rdirp)
    except subprocess.CalledProcessError as ex:
        log.exception("Unable to get git log: %r", ex.output)
        raise GitImportBadRepoError  # noqa: B904

    ret_git += f"\nCommit ID: {commit_id}"

    # get branch
    cmd = [
        "git",
        "symbolic-ref",
        "--short",
        "HEAD",
    ]
    try:
        branch = cmd_log(cmd, cwd=rdirp)
    except subprocess.CalledProcessError as ex:
        # I can't discover a way to exercise this, but git is complex
        # so still logging and raising here in case.
        log.exception("Unable to determine branch: %r", ex.output)
        raise GitImportBadRepoError  # noqa: B904

    ret_git += "{}Branch: {}".format("   \n", branch)

    # Get XML logging logger and capture debug to parse results
    output = StringIO()
    import_log_handler = logging.StreamHandler(output)
    import_log_handler.setLevel(logging.DEBUG)

    logger_names = [
        "xmodule.modulestore.xml_importer",
        "git_add_course",
        "xmodule.modulestore.xml",
        "xmodule.seq_module",
    ]
    loggers = []

    for logger_name in logger_names:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(import_log_handler)
        loggers.append(logger)

    try:
        import_cmd = importlib.import_module(
            "cms.djangoapps.contentstore.management.commands.import"
        )
        management.call_command(
            import_cmd.Command(),
            git_repo_dir,
            rdir,
            nostatic=not git_import_static,
            nopythonlib=not git_import_python_lib,
            python_lib_filename=python_lib_filename,
        )
    except CommandError:
        raise GitImportXmlImportFailedError  # noqa: B904
    except NotImplementedError:
        raise GitImportUnsupportedStoreError  # noqa: B904

    ret_import = output.getvalue()

    # Remove handler hijacks
    for logger in loggers:
        logger.setLevel(logging.NOTSET)
        logger.removeHandler(import_log_handler)

    course_key = None

    # extract course ID from output of import-command-run and make symlink
    # this is needed in order for custom course scripts to work
    match = re.search(r"(?ms)===> IMPORTING courselike (\S+)", ret_import)
    if match:
        course_id = match.group(1).split("/")
        # we need to transform course key extracted from logs into CourseLocator
        # instance, because we are using split module store and course keys store
        # as instance of CourseLocator.
        # Please see common.lib.xmodule.xmodule.modulestore.split_mongo.split.SplitMongoModuleStore#make_course_key  # noqa: E501
        # We want set course id in CourseGitLog as CourseLocator.
        # So that in split module environment course id remain consistent as
        # CourseLocator instance.
        course_key = CourseLocator(*course_id)
        update_outline_from_modulestore(course_key)
        SignalHandler.course_published.send(
            sender=course_key.course, course_key=course_key
        )
        cdir = f"{git_repo_dir}/{course_key.course}"
        log.debug("Studio course dir = %s", cdir)

        if os.path.exists(cdir) and not os.path.islink(cdir):  # noqa: PTH110, PTH114
            log.debug("   -> exists, but is not symlink")
            log.debug(
                subprocess.check_output(  # noqa: S603
                    [  # noqa: S607
                        "ls",
                        "-l",
                    ],
                    cwd=os.path.abspath(cdir),  # noqa: PTH100
                )
            )
            try:
                os.rmdir(os.path.abspath(cdir))  # noqa: PTH106, PTH100
            except OSError:
                log.exception("Failed to remove course directory")

        if not os.path.exists(cdir):  # noqa: PTH110
            log.debug("   -> creating symlink between %s and %s", rdirp, cdir)
            try:
                os.symlink(
                    os.path.abspath(rdirp),  # noqa: PTH100
                    os.path.abspath(cdir),  # noqa: PTH100
                )
            except OSError:
                log.exception("Unable to create course symlink")
            log.debug(
                subprocess.check_output(  # noqa: S603
                    [  # noqa: S607
                        "ls",
                        "-l",
                    ],
                    cwd=os.path.abspath(cdir),  # noqa: PTH100
                )
            )

    cgl = CourseGitLog.objects.create(
        course_id=course_key,
        repo_dir=rdir,
        created=timezone.now(),
        course_import_log=ret_import,
        git_log=ret_git,
    )

    log.debug(f"saved CourseGitLog for {cgl.course_id}")  # noqa: G004

    removed_logs_count = remove_old_course_import_logs(course_key)
    if removed_logs_count > 0:
        log.debug(
            f"removed {removed_logs_count} old CourseGitLog for {course_key}"  # noqa: G004
        )
