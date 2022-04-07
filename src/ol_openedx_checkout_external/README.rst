External Checkout Plugin
=============================

A django app plugin to add a new API to Open edX for external checkouts.
The plugin redirects the user the desired external ecommerce service upon clicking the **Upgrade** button in LMS dashboard or Learning MFE.


Installation
------------

You can install this plugin into any Open edX instance by using any of the following methods:


**Option 1: Install from PyPI**

.. code-block::

    # If running devstack in docker, first open a shell in LMS (make lms-shell)

    pip install ol-openedx-checkout-external


**Option 2: Build the package locally and install it**

Follow these steps in a terminal on your machine:

1. Navigate to ``open-edx-plugins`` directory
2. If you haven't done so already, run ``./pants build``
3. Run ``./pants package ::``. This will create a "dist" directory inside "open-edx-plugins" directory with ".whl" & ".tar.gz" format packages for all the "ol_openedx_*" plugins in "open-edx-plugins/src")
4. Move/copy any of the ".whl" or ".tar.gz" files for this plugin that were generated in the above step to the machine/container running Open edX (NOTE: If running devstack via Docker, you can use ``docker cp`` to copy these files into your LMS container)
5. Run a shell in the machine/container running Open edX, and install this plugin using pip

Configuration
------------

**1) edx-platform configuration**

You might need to add the following configuration values to the config file in Open edX. For any release after Juniper, that config file is ``/edx/etc/lms.yml``. These should be added to the top level. **Ask a fellow developer or devops for these values.**

.. code-block::


    1) MARKETING_SITE_CHECKOUT_URL=<checkout url of marketing site> # This settings is not part of Open Edx, It's added by this plugin
    2) ECOMMERCE_PUBLIC_URL_ROOT=<LMS_BASE_URL> (Because we want to use external ecommerce using this API plugin for redirection)
    3) Create an new ecommerce configuration in http://<LMS_BASE>/admin/commerce/commerceconfiguration with "basket_checkout_page=/checkout-external/" in the above ecommerce configuration


How To Use
----------

The API supports a GET call with sku as query parameter.

**API Request**

To manually call the API, Send a GET request to `<LMS_BASE>/checkout-external?sku=<sku_id>`:

A sample request looks like below:

.. code-block::


    http://localhost:18000/checkout-external?sku=ABC45F


**API Response**

The successful response would be a redirect to the marketing site with 302 status code:


.. code-block::

    With 302 (If your marketing checkout URL is "https://<marketing_site_base>/checkout")

    The resulting redirect would be:
    https://<marketing_site_base>/checkout/?course_id=<course_id against the sku in CourseMode>

    With 400

    {
        "developer_message": "<Message for the developer>",
        "error_code": "internal_error"
    }
