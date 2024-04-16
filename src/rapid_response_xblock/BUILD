python_sources(
    name="rapid_response_xblock",
    dependencies=[
        "src/rapid_response_xblock/migrations:rapid_response_migrations",
        "src/rapid_response_xblock/settings:rapid_response_settings",
        ],
)

python_distribution(
    name="rapid_response_xblock_package",
    dependencies=[
        ":rapid_response_xblock",
        "src/rapid_response_xblock/static/js:rapid_response_js",
        "src/rapid_response_xblock/static/css:rapid_response_css",
        "src/rapid_response_xblock/static/html:rapid_response_html",
    ],
    provides=setup_py(
        name="rapid-response-xblock",
        version="0.9.2",
        description="An Open edX plugin to add rapid response aside for problem xBlocks",
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
