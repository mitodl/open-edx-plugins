Staff Graded Assignment XBlock
==============================

This package provides an XBlock for use with the edX platform which
provides a staff graded assignment. Students are invited to upload files
which encapsulate their work on the assignment. Instructors are then
able to download the files and enter grades for the assignment.

Note that this package is both an XBlock and a Django application. 

Installation
------------


1. Install Package 

   installing manually for evaluation and testing:

   -  ``sudo su - edxapp -s /bin/bash``
   -  ``. edxapp_env``
   -  ``pip install -e git+https://github.com/mitodl/edx-sga@release#egg=edx-sga``

   installing in production:
	
   - In ``/edx/app/edxapp/edx-platform/requirements/edx/github.txt``, add:
   
     .. code:: sh
   
          -e git+https://github.com/mitodl/edx-sga@release#egg=edx-sga

2. Enable advanced components in LMS and Studio (CMS).

   -  In ``/edx/app/edxapp/edx-platform/lms/envs/common.py``, uncomment:

      .. code:: sh

          # from xmodule.x_module import prefer_xmodules  
          # XBLOCK_SELECT_FUNCTION = prefer_xmodules  

   -  In ``/edx/app/edxapp/edx-platform/cms/envs/common.py``, uncomment:

      .. code:: sh

          # from xmodule.x_module import prefer_xmodules  
          # XBLOCK_SELECT_FUNCTION = prefer_xmodules  

   -  In ``/edx/app/edxapp/edx-platform/cms/envs/common.py``, change:

      .. code:: sh

          'ALLOW_ALL_ADVANCED_COMPONENTS': False,

      to

      .. code:: sh

          'ALLOW_ALL_ADVANCED_COMPONENTS': True,
          
3. Configure file storage

   For file storage, SGA uses the same file storage configuration as other
   applications in edX, such as the comments server. If you change these
   settings to SGA it will also affect those other applications.

   devstack defaults to local storage, but fullstack defaults to S3. You have 
   two options in fullstack:
   
   1. Use local storage (useful for evaluation and testing)
   
      In ``/edx/app/edxapp/edx-platform/lms/envs/aws.py`` change:
      
      .. code:: sh

          DEFAULT_FILE_STORAGE = 'storages.backends.s3boto.S3BotoStorage'
      
      to:
      
      .. code:: sh

          DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
          MEDIA_ROOT = '/edx/var/edxapp/uploads'
   
   2. Use S3 storage (default)
   
      To enable S3 storage, set the following values in your
      ``/edx/app/edxapp/lms.auth.json`` file or, preferably, in your
      additional yaml overrides in your edx/configuration setup.

      .. code:: sh

          "AWS_ACCESS_KEY_ID": "your bucket AWS access key ID",
          "AWS_SECRET_ACCESS_KEY": "Your bucket AWS access key secret",
          "AWS_STORAGE_BUCKET_NAME": "Your upload bucket name",

Course Authoring in edX Studio
------------------------------

1. Change Advanced Settings

   1. Open a course you are authoring and select "Settings" ⇒ "Advanced
      Settings
   2. Navigate to the section titled "Advanced Module List"
   3. Add "edx\_sga" to module list.
   4. Studio should save your changes automatically.
   
.. figure:: https://github.com/mitodl/edx-sga/blob/screenshots/img/screenshot-studio-advanced-settings.png
   :alt: the Advanced Module List section in Advanced Settings
   
2. Create an SGA XBlock

   1. Return to the Course Outline
   2. Create a Section, Sub-section and Unit, if you haven't already
   3. In the "Add New Component" interface, you should now see an "Advanced" 
      button
   4. Click "Advanced" and choose "Staff Graded Assignment"
   
.. figure:: https://raw.githubusercontent.com/mitodl/edx-sga/screenshots/img/screenshot-studio-new-unit.png
   :alt: image

3. Write a question with an SGA response

   Since the Staff Graded Assignment doesn't support text within the problem, 
   it is recommended to precede the SGA XBlock with a Text or HTML XBlock with 
   instructions for the student. We recommend something using the following 
   template:
   
       Use the "Select a File" button below to choose the file you wish to have 
       graded. After you have chosen the file the button will change to the 
       name of the file. Click the button again to Upload.
       
       When the upload is complete, a link will appear with the name of your 
       file. Click it to confirm that the upload was successful. You can replace
       this file by simply selecting another file and uploading it. After
       the due date has passed, you will no longer be able to upload files. 
 
4. Settings

+----------------+--------------------------------------------------------------------------+
| display_name   | The name appears in the horizontal navigation at the top of the page     |
+----------------+--------------------------------------------------------------------------+
| Maximum Score  | Maximum grade score given to assignment by staff                         |
+----------------+--------------------------------------------------------------------------+
| Problem Weight | Defines the number of points each problem is worth.                      |
+----------------+--------------------------------------------------------------------------+

.. figure:: https://raw.githubusercontent.com/mitodl/edx-sga/screenshots/img/screenshot-studio-new-unit.png
   :alt: image
 
       
Course Authoring in XML
-----------------------

XML for an SGA XBlock consists of one tag with the three attributes mentioned
above. It is recommended to also include a url_name attribute. For example:

.. code:: XML

        <vertical display_name="Staff Graded Assignment">
            <edx_sga url_name="sga_example" weight="10.0" display_name="SGA Example" points="100.0" />
        </vertical>


Staff Grading
-------------

1. Navigate to the student view (LMS) of the course and find the vertical with 
   your Staff Graded Assignment. (If you are in Studio, click "View Live"). 
   
2. If you are Course Staff or an Instructor for the course, you will see a 
   "Grade Submissions" button in the lower right corner of the XBlock (Be sure 
   you are in "Staff View" indicated by a red label in the upper right corner of
   the page; if it says "Student View" in green, click on it once.)
   
.. figure:: https://raw.githubusercontent.com/mitodl/edx-sga/screenshots/img/screenshot-studio-new-unit.png
   :alt: image

3. Describe columns

4. Describe Staff workflow

5. Describe Student workflow

Advanced
--------

Access to files?

.. figure:: https://raw.githubusercontent.com/mitodl/edx-sga/screenshots/img/screenshot-studio-new-unit.png
   :alt: image


