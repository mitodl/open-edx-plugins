python_sources(
    name="openedx_companion_configuration",
    dependencies=[
        "src/openedx_companion_auth/settings:openedx_companion_auth_settings",
        "//:external_dependencies#pytest-mock",
        ],
)

python_distribution(
    name="openedx_companion_auth_package",
    dependencies=[
        ":openedx_companion_configuration",
    ],
    provides=setup_py(
        name="openedx-companion-auth",
        version="1.3.0",
        description="A package used for configuring/integrating Openedx auth with MIT projects",
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
