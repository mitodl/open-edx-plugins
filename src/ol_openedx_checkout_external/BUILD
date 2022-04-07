python_sources(
    name="external_checkout",
    dependencies=["src/ol_openedx_checkout_external/settings:checkout_external_settings"]
)

python_distribution(
    name="checkout_external_package",
    dependencies=[":external_checkout"],
    provides=setup_py(
        name="ol-openedx-checkout-external",
        version="0.1.0",
        description="An Open edX plugin to add API for external checkouts",
        entry_points={
            "lms.djangoapp": ["ol_openedx_checkout_external = ol_openedx_checkout_external.app:ExternalCheckoutConfig"],
            "cms.djangoapp": []
        }
    ),
)
