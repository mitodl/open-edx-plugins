Open edX auth companion
=======================

An Open edX plugin that redirects users from edx-platform to MIT applications

Version Compatibility
---------------------

Compatible with the Nutmeg release of the Open edX and onwards. May work with prior releases as well.

Installing The Plugin
---------------------

You can install this plugin into any Open edX instance by using any of the following methods:

**Option 1: Install from PyPI**

.. code-block::

    # If running devstack in docker, first open a shell in LMS (make lms-shell)

    pip install openedx-companion-auth


**Option 2: Build the package locally and install it**

Follow these steps in a terminal on your machine:

1. Navigate to ``open-edx-plugins`` directory
2. If you haven't done so already, run ``./pants build``
3. Run ``./pants package ::``. This will create a "dist" directory inside "open-edx-plugins" directory with ".whl" & ".tar.gz" format packages for all plugins in the src directory
4. Move/copy any of the ".whl" or ".tar.gz" files for this plugin that were generated in the above step to the machine/container running Open edX (NOTE: If running devstack via Docker, you can use ``docker cp`` to copy these files into your LMS or CMS containers)
5. Run a shell in the machine/container running Open edX, and install this plugin using pip


``Note``: In some cases you might need to restart edx-platform after installing the plugin to reflect the changes.

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
