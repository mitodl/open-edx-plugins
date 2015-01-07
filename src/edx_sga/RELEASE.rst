SGA 0.4.0 Release Notes
=======================

Migrations
----------

0.4.0 uses the edX Submissions API to submit grades. If you are upgrading from an 
earlier version and you have student submissions and grades that need to be migrated, 
you should run the migration script. 

.. code-block:: bash

  python manage.py lms --settings=aws sga_migrate_submissions DevOps/0.001/2015_Summer

Additions
---------

- Now supports basic workflow. Instructors must approve grades submitted by course staff.
- Added Staff Debug

Fixes
-----

- No longer requires students to re-visit SGA problems in order to record grades. 

