python_sources(
    name="ol_social_auth_source",
)

python_distribution(
    name="ol_social_auth_package",
    dependencies=[
        ":ol_social_auth_source",
    ],
    provides=setup_py(
        name="ol-social-auth",
        version="1.0.0",
        description="A package implementing MIT social auth backend",
        license="BSD-3-Clause",
        author="MIT Office of Digital Learning",
        include_package_data=True,
        zip_safe=False,
        keywords="Python edx"
    ),
)
