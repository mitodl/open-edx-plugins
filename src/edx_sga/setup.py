"""Setup for edx-sga XBlock."""

import os
from setuptools import setup, find_packages


def package_data(pkg, root):
    """Generic function to find package_data for `pkg` under `root`."""
    data = []
    for dirname, _, files in os.walk(os.path.join(pkg, root)):
        for fname in files:
            data.append(os.path.relpath(os.path.join(dirname, fname), pkg))

    return {pkg: data}


setup(
    name='edx-sga',
    version='0.1',
    description='edx-sga XBlock',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'XBlock',
    ],
    entry_points={
        'xblock.v1': [
            'edx_sga = edx_sga:StaffGradedAssignmentXBlock',
        ]
    },
    package_data=package_data("edx_sga", "static"),
)
