edx-sysadmin
=============================

This is a django app plugin extracted from `edx-platform <https://github.com/edx/edx-platform>`_ which enables certian users to perform some specific operations in Open edX environment (which are described under ``Features`` section below).
Earlier, ``Sysadmin Dashboard`` was a part of ``edx-platform``, however starting from `lilac release <https://github.com/edx/edx-platform/tree/open-release/lilac.master>`_ of Open edX the sysadmin panel has been removed
and transitioned to as separate plugin.

Note that the initial independent repository for this plugin was https://github.com/mitodl/edx-sysadmin. Now it has been migrated to open-edx-plugins.


NOTE:
It is recommended that you use edx-sysadmin plugin with Open edX's `lilac <https://github.com/edx/edx-platform/tree/open-release/lilac.master>`_ release and successors.
If you wish to use the ``Sysadmin Dashboard`` with Open edX releases before ``lilac`` you don't have to install this plugin and can simply enable ``ENABLE_SYSADMIN_DASHBOARD`` feature flag in environment files (e.g ``lms.yml`` or ``lms.env.json``) to access sysadmin dashboard features.

Version Compatibility
---------------------
**For "Lilac" or more recent release of edX platform**

Use any version of edx-sysadmin plugin.


**For releases prior to "Lilac"**

You do not need edx-sysadmin plugin. Just enable ``ENABLE_SYSADMIN_DASHBOARD`` feature flag in environment files (e.g ``lms.yml`` or ``lms.env.json``) to access sysadmin dashboard features.


Installing The Plugin
---------------------

You can install this plugin into any Open edX instance by using any of the following methods (See the note above for releases before `lilac`):


**Option 1: Install from PyPI**

.. code-block::

    # If running devstack in docker, first open a shell in LMS (make lms-shell)

    pip install edx-sysadmin


**Option 2: Build the package locally and install it**

Follow these steps in a terminal on your machine:

1. Navigate to ``open-edx-plugins`` directory
2. If you haven't done so already, run ``./pants build``
3. Run ``./pants package ::``. This will create a "dist" directory inside "open-edx-plugins" directory with ".whl" & ".tar.gz" format packages for "edx_sysadmin" and other "ol_openedx_*" plugins in "open-edx-plugins/src")
4. Move/copy any of the ".whl" or ".tar.gz" files for this plugin that were generated in the above step to the machine/container running Open edX (NOTE: If running devstack via Docker, you can use ``docker cp`` to copy these files into your LMS or CMS containers)
5. Run a shell in the machine/container running Open edX, and install this plugin using pip

* Once you have installed the plugin you can visit ``<EDX_BASE_URL>/sysadmin`` to access the plugin features.

``Note``: In some cases you might need to restart edx-platform after installing the plugin to reflect the changes.

Configurations
--------------
You have the following configuration properties to customize your plugin behavior:

* **GIT_REPO_DIR:** This path defines where the imported repositories will be places in storage. Default value is ``/edx/var/edxapp/course_repos``.
* **GIT_IMPORT_STATIC:** This is a boolean that tells the plugin to either load the static content from the course repo or not. Default value is ``True``
* **SYSADMIN_GITHUB_WEBHOOK_KEY:** This value is used to save either of ``sha256 or sha1`` hashes. (This key is only used for Github Webhooks). Default value is ``None``.
* **SYSADMIN_DEFAULT_BRANCH:** This value is used to specify environment specific branch name to be used for course reload/import through Github Webhooks. (This key is only used for Github Webhooks). Default value is ``None``

Features
--------

edx-sysadmin provides different features such as:

* Register Users:
    * You can ``register new user accounts`` with an easy to use form via ``Users`` tab.
* Delete Courses:
    * You can ``delete any course by using a course ID or directory`` via ``Courses`` tab.
* Git Import:
    * You can ``import any course maintained through a git repository`` via ``Git Import`` tab.
* Git Logs
    * You can ``check the logs for all imported courses`` through git via ``Git Logs`` tab.
* Git Reload (Not directly visible)
    * You can configure Github webhooks with this plugin to ensure reload/import of your courses on new commits
