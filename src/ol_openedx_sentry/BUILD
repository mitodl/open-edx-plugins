python_library(
    name="sentry_app",
    dependencies=["src/ol_openedx_sentry/settings:sentry_settings"]
)

python_distribution(
    name="sentry_package",
    dependencies=[":sentry_app"],
    provides=setup_py(
        name="ol-openedx-sentry",
        version="0.1.1",
        description="An Open edX plugin to enable error tracking with Sentry",
        entry_points={
            "lms.djangoapp": ["ol_openedx_sentry = ol_openedx_sentry.app:EdxSentry"],
            "cms.djangoapp": ["ol_openedx_sentry = ol_openedx_sentry.app:EdxSentry"]
        }
    ),
    setup_py_commands=["sdist", "bdist_wheel"]
)
