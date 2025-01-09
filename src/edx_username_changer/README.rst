Edx Username Changer
=======================

A plugin to enable update usernames through admin panel in Open edX (and other apps that log into Open edX via OAuth).

Version Compatibility
---------------------

It only supports koa and latest releases of Open edX.

Installing The Plugin
---------------------

You can install this plugin into any Open edX instance by using any of the following methods:

**Option 1: Install from PyPI**

.. code-block::

    # If running devstack in docker, first open a shell in LMS (make lms-shell)

    pip install edx-username-changer


**Option 2: Build the package locally and install it**

Follow these steps in a terminal on your machine:

1. Navigate to ``open-edx-plugins`` directory
2. Run ``./pants package ::``. This will create a "dist" directory inside "open-edx-plugins" directory with ".whl" & ".tar.gz" format packages for all plugins in the src directory
3. Move/copy any of the ".whl" or ".tar.gz" files for this plugin that were generated in the above step to the machine/container running Open edX (NOTE: If running devstack via Docker, you can use ``docker cp`` to copy these files into your LMS or CMS containers)
4. Run a shell in the machine/container running Open edX, and install this plugin using pip


``Note``: In some cases you might need to restart edx-platform after installing the plugin to reflect the changes.

Configurations
--------------
To configure this plugin, you need to do the following one step:

1. Add/Enable a feature flag (ENABLE_EDX_USERNAME_CHANGER) into your environment variables (through ``private.py`` in LMS or CMS, depending upon where you are installing the plugin)

.. code-block::

    FEATURES["ENABLE_EDX_USERNAME_CHANGER"] = True

How to use
----------
Its usage is as simple as changing the username of a user account through django's admin panel. Here are the steps (for clarity):

1. Install edx-username-changer plugin.
2. Use an admin account to access django admin panel.
3. Go to Users model and select an account to change its username.
4. In the account editor page change the username field.
5. Hit Save (present at the bottom-right of page).

The whole process can be done on lms or studio or on both of them.
