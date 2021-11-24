ol_openedx_canvas_integration
=============================

A django app plugin for edx-platform to add Canvas Integration support.

**NOTE:**

Since the edx-platform’s ``Instructor Dashboard`` does not support the plugin based tabs so we had to make some changes in the edx-platform itself to add ``Canvas`` tab through the plugin.

The ``edx-platform`` branch/tag you're using must include below commit for ``ol-openedx-canvas-integration`` plugin to work properly:

- https://github.com/mitodl/edx-platform/commit/5b8acfceb7fcebab6b5e3aff0493876f439f2b80


Installation
------------

You can install it into any Open edX instance by using the following two methods:

- To get the latest stable release from PyPI

.. code-block::


    pip install ol-openedx-canvas-integration


- To create & install a build locally

.. code-block::

    In terminal/shell navigate to `open-edx-plugins` directory
    Run `./pants build` (If you haven’t run it already)
    Run `./pants package ::` (This command will create a `dist` directory inside `open-edx-plugins` directory with `.whl` & `.tar.gz` format packages of all the plugins present in `open-edx-plugins`)
    Install the `ol-openedx-canvas-integration` using any of `.whl` or `.tar.gz` files created in the above step


Dependencies
------------

Once you’ve installed the plugin you will need set some configuration values as mentioned below.

.. code-block::

    Go to Studio (`http://localhost:18010`), Open a course and navigate to `Advanced Settings`, Set value for `canvas_course_id` (This is the Id of a course that’s on Canvas)
    Set the value for `CANVAS_ACCESS_TOKEN` into your environment variable (through lms.yml)
    Set the value for `CANVAS_BASE_URL` (This will be the URL of your Canvas instance)

How To Use
----------

1) Install `ol-openedx-canvas-integration` plugin & set the configurations as mentioned above

2) In Studio(`http://localhost:18010`) create/navigate to a course and create some graded assignments/quizes

3) In LMS (`http://localhost:18000`), open the above course, navigate to `Instructor` tab & make sure that you see `Canvas` underneath

4) Clicking the `Canvas` tab should present you with a multiple buttons `List enrolments on Canvas`, `Merge enrolment list using Canvas`, `Overload enrolment list using Canvas`, `Push all MITx grades to Canvas`, `List Canvas assignments`

    4.1) Clicking `List enrolments on Canvas` button should list all the enrollments for the course on Canvas

    4.2 Clicking `Merge enrolment list using Canvas` should enroll all the users that are present on edX. For the users that doesn’t exist on edX it will create `CourseEnrollmentAllowed` object

    4.3 Clicking `Overload enrolment list using Canvas` will manage both enroll and unenroll

    4.4 Clicking `Push all MITx grades to Canvas` will create those assignments/quizes in Canvas that don’t exist there and then it will created/update the user grades for those assignments/quizes in the Canvas (Make sure that the assignment that you’re syncing grades for has a `Published` status on Canvas)

    4.5 Clicking `List Canvas assignments` will show a dropdown of all the assignments that are present on Canvas and upon clicking an assignment in dropdown a list of grades will be printed.
