python_sources(
    name="canvas_integration",
    dependencies=["src/ol_openedx_canvas_integration/settings:canvas_settings"],
)

python_distribution(
    name="canvas_integration_package",
    dependencies=[
        ":canvas_integration",
        "src/ol_openedx_canvas_integration/static/js:canvas_js",
        "src/ol_openedx_canvas_integration/templates:canvas_templates",
    ],
    provides=setup_py(
        name="ol-openedx-canvas-integration",
        version="0.5.0",
        description="An Open edX plugin to add canvas integration support",
        license="BSD-3-Clause",
        entry_points={
            "lms.djangoapp": [
                "ol_openedx_canvas_integration = ol_openedx_canvas_integration.app:CanvasIntegrationConfig"
            ],
            "cms.djangoapp": [
                "ol_openedx_canvas_integration = ol_openedx_canvas_integration.app:CanvasIntegrationConfig"
            ],
        },
    ),
)

python_tests(
    name="tests",
)
