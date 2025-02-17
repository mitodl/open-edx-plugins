Open edX auth companion
=======================

An Open edX plugin that redirects users from edx-platform to MIT applications

Version Compatibility
---------------------

Compatible with the Nutmeg release of the Open edX and onwards. May work with prior releases as well.

Installing The Plugin
---------------------

For detailed installation instructions, please refer to the `plugin installation guide <../../docs#installation-guide>`_.``

Installation required in:

* LMS

Configurations
--------------
You have the following configuration properties to customize your plugin behavior:

* **MITX_REDIRECT_ENABLED:** The middleware checks this value and redirects only when it is set to ``True``.
* **MITX_REDIRECT_LOGIN_URL:** The URL where the user is redirected for login.
* **MITX_REDIRECT_ALLOW_RE_LIST:** A list of paths on which the middleware does not redirect to the ``MITX_REDIRECT_LOGIN_URL``.
* **MITX_REDIRECT_DENY_RE_LIST:** A list of paths on which the middleware redirects to the ``MITX_REDIRECT_LOGIN_URL``.

Working
--------
* Install the plugin in the lms following the installation steps above.
* Verify that you are not logged in on edx-platform.
* Go to `localhost:18000`. You should be redirected to the ``MITX_REDIRECT_LOGIN_URL``
