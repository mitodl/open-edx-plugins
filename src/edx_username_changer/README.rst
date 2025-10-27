edX Username Changer
=======================

A plugin to enable update usernames through admin panel in Open edX (and other apps that log into Open edX via OAuth).

Version Compatibility
---------------------

It only supports koa and latest releases of Open edX.

Forum Backend Support
~~~~~~~~~~~~~~~~~~~~~

**Important:** This plugin only supports the MySQL-based Forum v2 backend.
The MongoDB forum backend is NOT supported and will result in incorrect user
records being created when usernames are changed.

Before using this plugin, verify that your Open edX installation is configured
to use the MySQL backend for discussions/forums.

Installing The Plugin
---------------------

For detailed installation instructions, please refer to the `plugin installation guide <../../docs#installation-guide>`_.

Installation required in:

* LMS
* CMS

Configurations
--------------
To configure this plugin, you need to do one of the following steps:

- Add the following configuration values to the config file in Open edX. For any release after Juniper, that config file is ``/edx/etc/lms.yml``. If you're using ``private.py``, add these values to ``lms/envs/private.py``. These should be added to the top level. **Ask a fellow developer or devops for these values.**

  .. code-block::

    FEATURES["ENABLE_EDX_USERNAME_CHANGER"] = True


- For Tutor installations, these values can also be managed through a `custom tutor plugin <https://docs.tutor.edly.io/tutorials/plugin.html#plugin-development-tutorial>`_.

How to use
----------
Its usage is as simple as changing the username of a user account through django's admin panel. Here are the steps (for clarity):

1. Install edx-username-changer plugin.
2. Use an admin account to access django admin panel.
3. Go to Users model and select an account to change its username.
4. In the account editor page change the username field.
5. Hit Save (present at the bottom-right of page).

The whole process can be done on lms or studio or on both of them.
