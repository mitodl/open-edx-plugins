External Checkout Plugin
=============================

A django app plugin to add a new API to Open edX for external checkouts.
The plugin redirects the user the desired external ecommerce service upon clicking the **Upgrade** button in LMS dashboard or Learning MFE.


Installation
------------

For detailed installation instructions, please refer to the `plugin installation guide <../../docs#installation-guide>`_.``

Installation required in:

* LMS

Configuration
-------------

**1) edx-platform configuration (Environment/Settings)**

You might need to add the following configuration values to the config file in Open edX. For any release after Juniper, that config file is ``/edx/etc/lms.yml``. These should be added to the top level. **Ask a fellow developer or devops for these values.**

.. code-block::

    MARKETING_SITE_CHECKOUT_URL = <MARKETING_SITE_CHECKOUT_URL>  # The URL of checkout/cart API in your marketing site
    ECOMMERCE_PUBLIC_URL_ROOT = <LMS_BASE_URL>  # Because we want to use external ecommerce using this API plugin for redirection


**2) edx-platform configuration (Django Admin)**

::

    1. Create a new ecommerce configuration in http://<LMS_BASE>/admin/commerce/commerceconfiguration with following values:

        a. Set value for "Basket checkout page" to "/checkout-external/". (When set, the ecommerce will redirect the `Upgrade Course` requests to this plugin)

        b. "Enabled" checked.

        c. "Checkout on ecommerce service" checked.

        d. Other values are arbitrary, but you can fill them out as per your need.

    2. Make sure to create CourseModes(e.g. "Verified") for the courses with non-empty and unique SKU value.


How To Use
----------

The API supports a GET call with SKU as query parameter.

**API Request**

To manually call the API, Send a GET request to ``<LMS_BASE>/checkout-external?sku=<sku_id>``:

A sample request looks like below:

::

    http://localhost:18000/checkout-external?sku=ABC45F


API Response
------------

The successful response would be a redirect to the marketing site with ``302`` status code and a failure response would be a ``400`` status code with basic error fields.


::

    With 302 status code (If your marketing checkout URL is "https://<marketing_site_base>/checkout") the resulting redirect would be:

    https://<marketing_site_base>/checkout/?course_id=<course_id against the sku in CourseMode>

::

    With 400 status code

    {
        "developer_message": "<Message for the developer>",
        "error_code": "internal_error"
    }
