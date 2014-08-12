Staff Graded Assignment XBlock
==============================

This package provides an XBlock for use with the edX platform which provides a staff graded assignment. Students are invited to upload files which encapsulate their work on the assignment. Instructors are then able to download the files and enter grades for the assignment.

Note that this package is both an XBlock and a Django application. For installation:

-   Install this package as an egg into the same environment as the edX platform using pip install.
-   Add edx\_sga to INSTALLED\_APPS in your Django settings.
-   Log in to Studio, navigate to a course you are authoring, and select "Settings" -\> "Advanced Settings". Extend the key "advanced\_modules" to include "edx\_sga" in the list modules.

Now when you add an "Advanced" unit in Studio, "Staff Graded Asssignment" will be an option:

![image](/../screenshots/img/screenshot-studio-new-unit.png?raw=tru)
