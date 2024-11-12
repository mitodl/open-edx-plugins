python_sources(
    name="ol_openedx_chat",
    dependencies=[
        "src/ol_openedx_chat/settings:ol_chat_settings",
        ],
)

python_distribution(
    name="ol_openedx_chat_package",
    dependencies=[
        ":ol_openedx_chat",
        "src/ol_openedx_chat/static/js:ol_chat_js",
        "src/ol_openedx_chat/static/css:ol_chat_css",
        "src/ol_openedx_chat/static/html:ol_chat_html",
    ],
    provides=setup_py(
        name="ol-openedx-chat",
        version="0.1.0",
        description="An Open edX plugin to add OL AI chat to xBlocks",
        license="BSD-3-Clause",
        author="MIT Office of Digital Learning",
        include_package_data=True,
        zip_safe=False,
        keywords="Python edx",
        entry_points={
            'xblock_asides.v1': [
            'ol_openedx_chat = ol_openedx_chat.block:OLChatAside',
        ],
            "lms.djangoapp": [
                "ol_openedx_chat = ol_openedx_chat.apps:OlOpenedxChatConfig"
            ],
            "cms.djangoapp": [
                "ol_openedx_chat = ol_openedx_chat.apps:OlOpenedxChatConfig"
            ],
        },
    ),
)

python_tests(
    name="tests",
)
