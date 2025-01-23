python_sources(
    name="openedx_companion_configuration",
    dependencies=[
        "src/openedx_companion_auth/settings:openedx_companion_auth_settings",
        ],
)

python_distribution(
    name="openedx_companion_auth_package",
    dependencies=[
        ":openedx_companion_configuration",
    ],
    provides=setup_py(
        name="openedx-companion-auth",
        version="1.1.1",
        description="A package to add login redirection from Open edX to MIT applications",
        license="BSD-3-Clause",
        author="MIT Office of Digital Learning",
        include_package_data=True,
        zip_safe=False,
        keywords="Python edx",
        entry_points={
            "lms.djangoapp": [
                "openedx_companion_auth = openedx_companion_auth.apps:MITxCoreConfig"
            ],
            "cms.djangoapp": [],
        },
    ),
)
