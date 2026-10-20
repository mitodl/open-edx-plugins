"""
Module for StaffGradedAssignmentXBlock.
"""

from importlib.metadata import PackageNotFoundError, version

# Read from the installed distribution, so pyproject.toml stays the only
# place a release bumps the version.
try:
    __version__ = version("edx-sga")
except PackageNotFoundError:  # imported from a checkout that is not installed
    __version__ = "unknown"
