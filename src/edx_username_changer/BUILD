python_sources(
    name="edx_username_changer_source",
    dependencies=["src/edx_username_changer/settings:edx_username_changer_settings"],
)

python_distribution(
    name="edx_username_changer_package",
    dependencies=[
        ":edx_username_changer_source",
    ],
    provides=setup_py(
        name="edx-username-changer",
        version="0.3.2",
        description="An edX plugin to change username of edx accounts through admin panel",
        license="BSD-3-Clause",
        author="MIT Office of Digital Learning",
        include_package_data=True,
        zip_safe=False,
        keywords="Python edx",
        entry_points={
            "lms.djangoapp": [
                "edx_username_changer = edx_username_changer.apps:EdxUsernameChangerConfig",
            ],
            "cms.djangoapp": [
                "edx_username_changer = edx_username_changer.apps:EdxUsernameChangerConfig",
            ],
        },
    ),
)
