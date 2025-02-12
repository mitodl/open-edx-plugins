Edx Username Changer
=======================

A plugin to enable update usernames through admin panel in Open edX (and other apps that log into Open edX via OAuth).

Version Compatibility
---------------------

It only supports koa and latest releases of Open edX.

Installing The Plugin
---------------------

For detailed installation instructions, please refer to the `plugin installation guide <../#installation-guide>`_

Installation required in:

* LMS

Configurations
--------------
To configure this plugin, you need to do one of the following steps:

1. Add/Enable a feature flag (ENABLE_EDX_USERNAME_CHANGER) into your environment variables (through ``private.py`` in LMS)

.. code-block::

    FEATURES["ENABLE_EDX_USERNAME_CHANGER"] = True

2. Add/Enable a feature flag (ENABLE_EDX_USERNAME_CHANGER) into your environment variables (through ``lms.env.yml`` file)

.. code-block::

    FEATURES:
      ...
      ENABLE_EDX_USERNAME_CHANGER: True
      ...


How to use
----------
Its usage is as simple as changing the username of a user account through django's admin panel. Here are the steps (for clarity):

1. Install edx-username-changer plugin.
2. Use an admin account to access django admin panel.
3. Go to Users model and select an account to change its username.
4. In the account editor page change the username field.
5. Hit Save (present at the bottom-right of page).

The whole process can be done on lms or studio or on both of them.
