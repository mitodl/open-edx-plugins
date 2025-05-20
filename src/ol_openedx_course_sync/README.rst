OL Open edX Course Sync
=======================

An Open edX plugin to sync course changes to its reruns.

Version Compatibility
---------------------

It supports Open edX releases from `Sumac` and onwards.

Installing The Plugin
---------------------

For detailed installation instructions, please refer to the `plugin installation guide <../../docs#installation-guide>`_.

Installation required in:

* CMS

Usage
-----

1. Install the plugin and run the migrations in the CMS.
2. Add the parent/source organization in the CMS admin model `CourseSyncParentOrg`.
  #. Course sync will only work for this organization. It will treat all the courses under this organization as parent/source courses.
3. The plugin will automatically add course re-runs created from the CMS as the child courses.
  #. The organization can be different for the reruns.
4. Target/child/rerun courses can be managed in the CMS admin model `CourseSyncMap`.
  #. You can update the comma-separated target course list.
5. Now, any changes made in the parent/source course will be synced to the target/child/rerun courses.
