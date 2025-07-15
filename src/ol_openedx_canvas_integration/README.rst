Canvas Integration Plugin
=============================

A django app plugin to add Canvas integration to Open edX.

**NOTE:**

We had to make some changes to edx-platform itself in order to add the "Canvas" tab to the instructor dashboard.

The ``edx-platform`` branch/tag you're using must include one of the below commit for ``ol-openedx-canvas-integration`` plugin to work properly:

**For "Sumac" or more recent release of edX platform, you should cherry-pick below commit:**

TBA - Will be added when we merge the PR in edx-platform

**For "Quince" to "Redwood" release of edX platform, you should cherry-pick below commit:**

https://github.com/mitodl/edx-platform/commit/7a2edd5d29ead6845cb33d2001746207cf696383

**For "Nutmeg" to "Palm" release of edX platform, you should cherry-pick below commit:**

- https://github.com/mitodl/edx-platform/pull/297/commits/c354a99bd14393b89a780692d07b6e70b586d172

**For any release prior to "Nutmeg" you should cherry-pick below commit:**

- https://github.com/mitodl/edx-platform/pull/274/commits/97a51d208f3cdfd26df0a62281b0964de10ff40a


Version Compatibility
---------------------

**For "Sumac" or more recent release of edX platform**

Use ``0.4.0`` or a above version of this plugin

**For "Quince" to "Redwood" release of edX platform**

Use ``0.3.0`` or a above version of this plugin

**For "Nutmeg" to "Palm" release of edX platform**

Use ``0.2.4`` or a above version of this plugin

**For releases prior to "Nutmeg"**

Use ``0.1.1`` version of this plugin

Installation
------------

For detailed installation instructions, please refer to the `plugin installation guide <../../docs#installation-guide>`_.

Installation required in:

* LMS
* CMS

Configuration
-------------

**1) edx-platform configuration**

- Add the following configuration values to the config file in Open edX. For any release after Juniper, that config file is ``/edx/etc/lms.yml``. If you're using ``private.py``, add these values to ``lms/envs/private.py``. These should be added to the top level. **Ask a fellow developer or devops for these values.**

  .. code-block::

    CANVAS_ACCESS_TOKEN: <some access token value>
    CANVAS_BASE_URL: <the base URL where Canvas is running>

- Add the following configuration to you CMS settings (depending on you deployment method). These values defined in the LMS settings and are used in `tasks.py`. Since Celery's auto-discovery imports this automatically in the CMS worker, these values need to be defined in the CMS settings to avoid Celery worker failure.

  .. code-block::

    BULK_EMAIL_MAX_RETRIES = 5
    BULK_EMAIL_DEFAULT_RETRY_DELAY = 30

- For Tutor installations, these values can also be managed through a `custom tutor plugin <https://docs.tutor.edly.io/tutorials/plugin.html#plugin-development-tutorial>`_.

**2) Add course settings value**

1) Open your course in Studio.
2) Navigate to "Advanced Settings".
3) Enable other course settings by enabling ``ENABLE_OTHER_COURSE_SETTINGS`` feature flag in CMS
4) Open course advanced settings in Open edX CMS, Add a dictionary in ``{"canvas_id": <canvas_course_id>}``. The ``canvas_course_id`` should be the id of a course that exists on Canvas. (NOTE: Canvas tab would only be visible if this value is set)


How To Use
----------

Manual Operations
^^^^^^^^^^^^^^^^^

1. In Studio, create/navigate to a course and create some graded assignments/quizzes.
2. In LMS, open the above course, navigate to the "Instructor" tab, and make sure that you see can see a "Canvas" tab.


Some of the functionality available in this tab:

- ``List enrollments on Canvas`` - Show all enrollments for the course on Canvas.
- ``Merge enrollment list using Canvas`` - Enroll all the users that are present on edX. For the users that don't exist on edX, a ``CourseEnrollmentAllowed`` object will be created.
- ``Overload enrollment list using Canvas`` - Ensure that enrollment records in edX match the enrollments in Canvas (i.e.: create any enrollments that exist in Canvas but don't exist in edX, and delete enrollments that exist in edX but not in Canvas)
- ``Push all MITx grades to Canvas`` - Ensure that Canvas has the equivalent assignments/quizzes for the course, and create/update the user grades for those assignments/quizzes in Canvas (The assignments must have a `Published` status on Canvas)
- ``List Canvas assignments`` - Show a dropdown of all the assignments that are present on Canvas, and upon selecting an assignment, show a list of grades.

Background Operations
^^^^^^^^^^^^^^^^^^^^^

When a Canvas course is linked by adding the ``canvas_id`` the **Advanced Settings** of a course, the following background operations are performed based on user events.

1. Automatic Syncing of Assignments
"""""""""""""""""""""""""""""""""""

Whenever the course is **Published** from the Studio, the **graded subsections** of the Open edX Course are automatically synced to the linked Canvas course. This includes

* adding new assignments when new graded subsections are added
* updating the existing assignments
* removing any assignment that might exist, when subsections are removed

.. IMPORTANT::
   The assignments that are updated in Canvas are set to "Unpublished" state by default. Instructors will have to manually publish them in Canvas to make it available to students.

2. Automatic Syncing of Grades
""""""""""""""""""""""""""""""

Whenever a learner interacts with a graded question in Open edX, the latest grades are automatically posted to Canvas, if it's a part of a synced assignment.
