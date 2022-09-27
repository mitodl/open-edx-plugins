python_sources(
    name="edx_logging",
    dependencies=[
        "src/ol_openedx_logging/settings",
        "//:external_dependencies#python-json-logger",
    ],
)

python_distribution(
    name="logging_package",
    dependencies=[":edx_logging"],
    provides=setup_py(
        name="ol-openedx-logging",
        version="0.1.0",
        description="An Open edX plugin to customize the logging configuration used by the edx-platform application",
        license="BSD-3-Clause",
        entry_points={
            "lms.djangoapp": [
                "ol_openedx_logging = ol_openedx_logging.app:EdxLoggingLMS"
            ],
            "cms.djangoapp": [
                "ol_openedx_logging = ol_openedx_logging.app:EdxLoggingCMS"
            ],
        },
    ),
)
