python_sources(
    name="rapid_response_xblock",
    dependencies=[
        "src/rapid_response_xblock/migrations:rapidresponse_migrations",
        "src/rapid_response_xblock/settings:rapidresponse_settings",
        "//:external_dependencies#edx-opaque-keys",
        "//:external_dependencies#XBlock",
        "//:external_dependencies#Django",

        ],
)

python_distribution(
    name="rapid_response_xblock_package",
    dependencies=[
        ":rapid_response_xblock",
        "src/rapid_response_xblock/static/js:rapidresponse_js",
        "src/rapid_response_xblock/static/css:rapidresponse_css",
        "src/rapid_response_xblock/static/html:rapidresponse_html",
    ],
    provides=setup_py(
        name="rapid-response-xblock",
        version="0.9.1",
        description="An xblock aside for problem xblocks",
        license="BSD-3-Clause",
        author="MIT Office of Digital Learning",
        include_package_data=True,
        zip_safe=False,
        keywords="Python edx",
        entry_points={
            'xblock_asides.v1': [
            'rapid_response_xblock = rapid_response_xblock.block:RapidResponseAside',
        ],
            "lms.djangoapp": [
                "rapid_response_xblock = rapid_response_xblock.apps:RapidResponseAppConfig"
            ],
            "cms.djangoapp": [
                "rapid_response_xblock = rapid_response_xblock.apps:RapidResponseAppConfig"
            ],
        },
    ),
)

python_tests(
    name="tests",
)
