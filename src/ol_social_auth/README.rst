Open Learning Social Auth
=======================

An Open edX plugin implementing MIT social auth backend

Version Compatibility
---------------------

Compatible with all edx releases

Installing The Plugin
---------------------

You can install this plugin into any Open edX instance by using any of the following methods:

**Option 1: Install from PyPI**

.. code-block::

    # If running devstack in docker, first open a shell in LMS (make lms-shell)

    pip install ol-social-auth


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
This section outlines the steps for integrating your application with ol-social-auth for various deployment scenarios. Please refer to the corresponding documentation for detailed instructions.

* **Devstack:** To configure ol-social-auth with an edx-platform instance provisioned using devstack, follow the instructions `here <https://mitodl.github.io/handbook/openedx/MITx-edx-integration-devstack.html>`_
* **Tutor:** To configure ol-social-auth with an edx-platform instance provisioned using tutor, follow the instructions `here https://mitodl.github.io/handbook/openedx/MITx-edx-integration-tutor.html`_


How to use
----------
Make sure to properly configure the plugin following the links in the above "Configurations" section before use.

* Install the plugin in the lms following the installation steps above.
* Verify that you are not logged in on edx-platform.
* Create a new user in your MIT application and verify that a corresponding user is successfully created on the edX platform.
