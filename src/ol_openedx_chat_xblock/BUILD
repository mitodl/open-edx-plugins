python_sources(
    name="ol_openedx_chat_xblock",
    dependencies=[
        "src/ol_openedx_chat_xblock/settings:ol_chat_xblock_settings",
        ],
)

python_distribution(
    name="ol_openedx_chat_xblock_package",
    dependencies=[
        ":ol_openedx_chat_xblock",
        "src/ol_openedx_chat_xblock/static/js:ol_chat_xblock_js",
        "src/ol_openedx_chat_xblock/static/css:ol_chat_xblock_css",
        "src/ol_openedx_chat_xblock/static/html:ol_chat_xblock_html",
    ],
    provides=setup_py(
        name="ol-openedx-chat-xblock",
        version="0.1.0",
        description="An Open edX xBlock to add Open Learning AI chat",
        license="BSD-3-Clause",
        author="MIT Office of Digital Learning",
        include_package_data=True,
        zip_safe=False,
        keywords="Python edx",
        entry_points={
            'xblock.v1': [
            'ol_openedx_chat_xblock = ol_openedx_chat_xblock.block:OLChatXBlock',
        ],
            "lms.djangoapp": [
                "ol_openedx_chat_xblock = ol_openedx_chat_xblock.apps:OLOpenedxChatXBlockConfig"
            ],
            "cms.djangoapp": [
                "ol_openedx_chat_xblock = ol_openedx_chat_xblock.apps:OLOpenedxChatXBlockConfig"
            ],
        },
    ),
)

python_tests(
    name="tests",
)
