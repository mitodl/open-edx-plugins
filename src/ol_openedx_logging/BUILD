python_library(
    name="edx_logging",
    dependencies=[
        "src/ol_openedx_logging/settings",
        "//:python-json-logger",
    ]
)

python_distribution(
    name="logging_package",
    dependencies=[":edx_logging"],
    provides=setup_py(
        name="ol-openedx-logging",
        version="0.1.0",
        description="An Open edX plugin to customize the logging configuration used by the edx-platform application",
        entry_points={
            "lms.djangoapp": ["ol_openedx_logging = ol_openedx_logging.app:EdxLoggingLMS"],
            "cms.djangoapp": ["ol_openedx_logging = ol_openedx_logging.app:EdxLoggingCMS"]
        }
    ),
    setup_py_commands=["sdist", "bdist_wheel"]
)
