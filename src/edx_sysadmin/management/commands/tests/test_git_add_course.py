"""
Provide tests for git_add_course management command.
"""
# pylint: disable=wrong-import-order
import contextlib
import logging
import os
import shutil
import subprocess
from io import StringIO
from uuid import uuid4

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test.utils import override_settings
from edx_sysadmin import git_import
from edx_sysadmin.git_import import (
    GitImportBadRepoError,
    GitImportCannotPullError,
    GitImportError,
    GitImportNoDirError,
    GitImportRemoteBranchMissingError,
    GitImportUrlBadError,
)
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.django_utils import SharedModuleStoreTestCase


@override_settings(
    GIT_REPO_DIR=settings.TEST_ROOT / f"course_repos_{uuid4().hex}",
)
class TestGitAddCourse(SharedModuleStoreTestCase):
    """
    Tests the git_add_course management command for proper functions.
    """

    ENABLED_CACHES = ["default", "mongo_metadata_inheritance", "loc_cache"]

    def setUp(self):
        super().setUp()
        self.git_repo_dir = settings.GIT_REPO_DIR
        self.TEST_REPO = "https://github.com/edx/edx4edx_lite.git"
        self.TEST_COURSE_KEY = self.store.make_course_key("MITx", "edx4edx", "edx4edx")
        self.TEST_BRANCH = "testing_do_not_delete"
        self.TEST_BRANCH_COURSE_KEY = self.store.make_course_key(
            "MITx", "edx4edx_branch", "edx4edx"
        )

    def assert_command_failure_regexp(self, regex, *args):
        """
        Convenience function for testing command failures
        """  # noqa: D401
        with pytest.raises(CommandError, match=regex):
            call_command("git_add_course", *args, stderr=StringIO())

    def test_command_args(self):
        """
        Validate argument checking
        """
        # No argument given.
        self.assert_command_failure_regexp(
            "Error: the following arguments are required: repository_url"
        )
        # Extra/Un-named arguments given.
        self.assert_command_failure_regexp(
            "Error: unrecognized arguments: blah blah blah",
            "blah",
            "blah",
            "blah",
            "blah",
        )
        # Not a valid path.
        self.assert_command_failure_regexp(
            f"Path {self.git_repo_dir} doesn't exist, please create it,",
            "blah",
        )
        # Test successful import from command
        if not os.path.isdir(self.git_repo_dir):  # noqa: PTH112
            os.mkdir(self.git_repo_dir)  # noqa: PTH102
        self.addCleanup(shutil.rmtree, self.git_repo_dir)

        # Make a course dir that will be replaced with a symlink
        # while we are at it.
        if not os.path.isdir(self.git_repo_dir / "edx4edx"):  # noqa: PTH112
            os.mkdir(self.git_repo_dir / "edx4edx")  # noqa: PTH102

        call_command(
            "git_add_course",
            self.TEST_REPO,
            directory_path=self.git_repo_dir / "edx4edx_lite",
        )

        # Test with all three args (branch)
        call_command(
            "git_add_course",
            self.TEST_REPO,
            directory_path=self.git_repo_dir / "edx4edx_lite",
            repository_branch=self.TEST_BRANCH,
        )

    def test_add_repo(self):
        """
        Various exit path tests for test_add_repo
        """
        with pytest.raises(GitImportNoDirError):
            git_import.add_repo(self.TEST_REPO, None, None)

        os.mkdir(self.git_repo_dir)  # noqa: PTH102
        self.addCleanup(shutil.rmtree, self.git_repo_dir)

        with pytest.raises(GitImportUrlBadError):
            git_import.add_repo("foo", None, None)

        with pytest.raises(GitImportCannotPullError):
            git_import.add_repo("file:///foobar.git", None, None)

        # Test git repo that exists, but is "broken"
        bare_repo = os.path.abspath(  # noqa: PTH100
            "{}/{}".format(settings.TEST_ROOT, "bare.git")
        )
        os.mkdir(bare_repo)  # noqa: PTH102
        self.addCleanup(shutil.rmtree, bare_repo)
        subprocess.check_output(
            [  # noqa: S607, S603
                "git",
                "--bare",
                "init",
            ],
            stderr=subprocess.STDOUT,
            cwd=bare_repo,
        )

        with pytest.raises(GitImportBadRepoError):
            git_import.add_repo(f"file://{bare_repo}", None, None)

    def test_detached_repo(self):
        """
        Test repo that is in detached head state.
        """
        repo_dir = self.git_repo_dir
        # Test successful import from command
        with contextlib.suppress(OSError):
            os.mkdir(repo_dir)  # noqa: PTH102

        self.addCleanup(shutil.rmtree, repo_dir)
        git_import.add_repo(self.TEST_REPO, repo_dir / "edx4edx_lite", None)
        subprocess.check_output(
            [  # noqa: S607, S603
                "git",
                "checkout",
                "HEAD~2",
            ],
            stderr=subprocess.STDOUT,
            cwd=repo_dir / "edx4edx_lite",
        )
        with pytest.raises(GitImportCannotPullError):
            git_import.add_repo(self.TEST_REPO, repo_dir / "edx4edx_lite", None)

    def test_branching(self):
        """
        Exercise branching code of import
        """
        repo_dir = self.git_repo_dir
        # Test successful import from command
        if not os.path.isdir(repo_dir):  # noqa: PTH112
            os.mkdir(repo_dir)  # noqa: PTH102
        self.addCleanup(shutil.rmtree, repo_dir)

        # Checkout non existent branch
        with pytest.raises(GitImportRemoteBranchMissingError):
            git_import.add_repo(
                self.TEST_REPO, repo_dir / "edx4edx_lite", "asdfasdfasdf"
            )

        # Checkout new branch
        git_import.add_repo(self.TEST_REPO, repo_dir / "edx4edx_lite", self.TEST_BRANCH)
        def_ms = modulestore()
        # Validate that it is different than master
        assert def_ms.get_course(self.TEST_BRANCH_COURSE_KEY) is not None

        # Attempt to check out the same branch again to validate branch choosing
        # works
        git_import.add_repo(self.TEST_REPO, repo_dir / "edx4edx_lite", self.TEST_BRANCH)

        # Delete to test branching back to master
        def_ms.delete_course(self.TEST_BRANCH_COURSE_KEY, ModuleStoreEnum.UserID.test)
        assert def_ms.get_course(self.TEST_BRANCH_COURSE_KEY) is None
        git_import.add_repo(self.TEST_REPO, repo_dir / "edx4edx_lite", "master")
        assert def_ms.get_course(self.TEST_BRANCH_COURSE_KEY) is None
        assert def_ms.get_course(self.TEST_COURSE_KEY) is not None

    def test_branch_exceptions(self):
        """
        This wil create conditions to exercise bad paths in the switch_branch function.
        """
        # create bare repo that we can mess with and attempt an import
        bare_repo = os.path.abspath(  # noqa: PTH100
            "{}/{}".format(settings.TEST_ROOT, "bare.git")
        )
        os.mkdir(bare_repo)  # noqa: PTH102
        self.addCleanup(shutil.rmtree, bare_repo)
        subprocess.check_output(
            [  # noqa: S603, S607
                "git",
                "--bare",
                "init",
            ],
            stderr=subprocess.STDOUT,
            cwd=bare_repo,
        )

        # Build repo dir
        repo_dir = self.git_repo_dir
        if not os.path.isdir(repo_dir):  # noqa: PTH112
            os.mkdir(repo_dir)  # noqa: PTH102
        self.addCleanup(shutil.rmtree, repo_dir)

        rdir = f"{repo_dir}/bare"
        with pytest.raises(GitImportBadRepoError):
            git_import.add_repo(f"file://{bare_repo}", None, None)

        # Get logger for checking strings in logs
        output = StringIO()
        test_log_handler = logging.StreamHandler(output)
        test_log_handler.setLevel(logging.DEBUG)
        glog = git_import.log
        glog.addHandler(test_log_handler)

        # Move remote so fetch fails
        shutil.move(bare_repo, f"{settings.TEST_ROOT}/not_bare.git")
        try:
            git_import.switch_branch("master", rdir)
        except GitImportError:
            assert "Unable to fetch remote" in output.getvalue()
        shutil.move(f"{settings.TEST_ROOT}/not_bare.git", bare_repo)
        output.truncate(0)

        # Replace origin with a different remote
        subprocess.check_output(
            [  # noqa: S603, S607
                "git",
                "remote",
                "rename",
                "origin",
                "blah",
            ],
            stderr=subprocess.STDOUT,
            cwd=rdir,
        )
        with pytest.raises(GitImportError):
            git_import.switch_branch("master", rdir)
        assert "Getting a list of remote branches failed" in output.getvalue()
