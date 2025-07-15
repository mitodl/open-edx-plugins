Open Learning Social Auth
==========================

An Open edX plugin implementing MIT social auth backend

Version Compatibility
---------------------

Compatible with all edx releases

Installing The Plugin
---------------------

For detailed installation instructions, please refer to the `plugin installation guide <../../docs#installation-guide>`_.

Installation required in:

* LMS

Configurations
--------------
This section outlines the steps for integrating your application with ol-social-auth for various deployment scenarios. Please refer to the corresponding documentation for detailed instructions.

* **Devstack:** To configure ol-social-auth with an edx-platform instance provisioned using devstack, follow the instructions `here <https://mitodl.github.io/handbook/openedx/MITx-edx-integration-devstack.html>`_
* **Tutor:** To configure ol-social-auth with an edx-platform instance provisioned using tutor, follow the instructions `here also <https://mitodl.github.io/handbook/openedx/MITx-edx-integration-tutor.html>`_


How to use
----------
Make sure to properly configure the plugin following the links in the above "Configurations" section before use.

* Install the plugin in the lms following the installation steps above.
* Verify that you are not logged in on edx-platform.
* Create a new user in your MIT application and verify that a corresponding user is successfully created on the edX platform.
