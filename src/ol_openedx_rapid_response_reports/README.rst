Rapid Response Reports Plugin
=============================

Overview
--------

A django app plugin for edx-platform to enable "Rapid Response Reports" functionality in "Instructor" tab.


**NOTE:**

If you are using `Nutmeg <https://github.com/openedx/edx-platform/tree/open-release/nutmeg.master>`_ or a more recent release of open edX, You can skip the cherry-picking step mentioned below and just use ``0.2.0`` or above version of the plugin. For any releases prior to ``Nutmeg`` please keep reading below.

(For Open edX releases prior to `Nutmeg`) We had to make some changes to edx-platform itself in order to add the ``Rapid Responses`` tab to the instructor dashboard, so the ``edx-platform`` branch/tag you're using must include this commit for the plugin to work properly:

- https://github.com/mitodl/edx-platform/pull/275/commits/bcad8505918993dac7de099d8e9d48f868bceda7

Dependencies
---------------

This plugin generates reports for `Rapid Response xBlock <https://github.com/mitodl/rapid-response-xblock>`_ submissions, so you need to have that package installed in order to use this plugin. That package is on PyPI and can be installed via pip.

Installation
------------

For detailed installation instructions, please refer to the `plugin installation guide <../../docs#installation-guide>`_.``

Installation required in:

* LMS

How To Use
----------

1) Follow the `Rapid Response xBlock <https://github.com/mitodl/rapid-response-xblock>`_ instructions to create multiple choice problems, configure them for rapid response, open the problem for rapid responses, and add some submissions while the problem is open.
2) Log into the LMS as an admin/staff, open the rapid response-enabled course, and click "Instructor" tab. You should see a "Rapid Responses" tab.
3) Click the "Rapid Responses" tab. You should see a list of timestamped links. Clicking any of those links should download a CSV report.
