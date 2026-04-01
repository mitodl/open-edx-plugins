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

Expired Token Cleanup
---------------------
This plugin includes a scheduled Celery task (``clear_expired_tokens``) that automatically removes expired OAuth2 access tokens, refresh tokens, and grant tokens from the database.

**Behavior:**

* Runs every **Monday at 9:00 AM** (server time) via Celery Beat.
* Uses django-oauth-toolkit's ``clear_expired()`` to delete tokens that have exceeded the configured expiration threshold.
* Sets ``REFRESH_TOKEN_EXPIRE_SECONDS`` to **30 days** (overriding the edx-platform default of 90 days). Tokens revoked or expired longer than 30 days ago will be cleaned up.

**Note:** If running this plugin for the first time on a database with a large backlog of expired tokens (millions of rows), consider running the ``edx_clear_expired_tokens`` management command manually first to reduce the initial volume before relying on the scheduled task.
