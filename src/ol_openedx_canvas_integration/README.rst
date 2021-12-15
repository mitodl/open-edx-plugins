Canvas Integration Plugin
=============================

A django app plugin to add Canvas integration to Open edX.

**NOTE:**

We had to make some changes to edx-platform itself in order to add the "Canvas" tab to the instructor dashboard.

The ``edx-platform`` branch/tag you're using must include below commit for ``ol-openedx-canvas-integration`` plugin to work properly:

- https://github.com/mitodl/edx-platform/pull/274/commits/97a51d208f3cdfd26df0a62281b0964de10ff40a


Installation
------------

You can install this plugin into any Open edX instance by using any of the following methods:


**Option 1: Install from PyPI**

.. code-block::

    # If running devstack in docker, first open a shell in LMS (make lms-shell)

    pip install ol-openedx-canvas-integration


**Option 2: Build the package locally and install it**

Follow these steps in a terminal on your machine:

1. Navigate to ``open-edx-plugins`` directory
2. If you haven't done so already, run ``./pants build``
3. Run ``./pants package ::``. This will create a "dist" directory inside "open-edx-plugins" directory with ".whl" & ".tar.gz" format packages for all the "ol_openedx_*" plugins in "open-edx-plugins/src")
4. Move/copy any of the ".whl" or ".tar.gz" files for this plugin that were generated in the above step to the machine/container running Open edX (NOTE: If running devstack via Docker, you can use ``docker cp`` to copy these files into your LMS container)
5. Run a shell in the machine/container running Open edX, and install this plugin using pip

Configuration
------------

**1) edx-platform configuration**

Add the following configuration values to the config file in Open edX. For any release after Juniper, that config file is ``/edx/etc/lms.yml``. These should be added to the top level. **Ask a fellow developer or devops for these values.**

.. code-block::


    CANVAS_ACCESS_TOKEN: <some access token value>
    CANVAS_BASE_URL: <the base URL where Canvas is running>

**2) Add course settings value**

1) Open your course in Studio.
2) Navigate to "Advanced Settings".
3) Add a ``canvas_course_id`` value. This should be the id of a course that exists on Canvas.


How To Use
----------

1. In Studio, create/navigate to a course and create some graded assignments/quizzes.
2. In LMS, open the above course, navigate to the "Instructor" tab, and make sure that you see can see a "Canvas" tab.


Some of the functionality available in this tab:

- ``List enrollments on Canvas`` - Show all enrollments for the course on Canvas.
- ``Merge enrollment list using Canvas`` - Enroll all the users that are present on edX. For the users that don't exist on edX, a ``CourseEnrollmentAllowed`` object will be created.
- ``Overload enrollment list using Canvas`` - Ensure that enrollment records in edX match the enrollments in Canvas (i.e.: create any enrollments that exist in Canvas but don't exist in edX, and delete enrollments that exist in edX but not in Canvas)
- ``Push all MITx grades to Canvas`` - Ensure that Canvas has the equivalent assignments/quizzes for the course, and create/update the user grades for those assignments/quizzes in Canvas (The assignments must have a `Published` status on Canvas)
- ``List Canvas assignments`` - Show a dropdown of all the assignments that are present on Canvas, and upon selecting an assignment, show a list of grades.