python_sources(
    name="canvas_integration",
    dependencies=["src/ol_openedx_canvas_integration/settings:canvas_settings"],
)

resources(
  name="canvas_plugin_templates",
  sources=[],
  dependencies=["src/ol_openedx_canvas_integration/templates:canvas_templates"]
)

resources(
  name="canvas_plugin_js",
  sources=[],
  dependencies=["src/ol_openedx_canvas_integration/static/js:canvas_js"]
)

python_distribution(
    name="canvas_integration_package",
    dependencies=[":canvas_integration", ":canvas_plugin_templates", ":canvas_plugin_js"],
    provides=setup_py(
        name="ol-openedx-canvas-integration",
        version="0.2.0",
        description="An Open edX plugin to add canvas integration support",
        license="BSD-3-Clause",
        entry_points={
            "lms.djangoapp": [
                "ol_openedx_canvas_integration = ol_openedx_canvas_integration.app:CanvasIntegrationConfig"
            ],
            "cms.djangoapp": [],
        },
    ),
)

python_tests(
    name="tests",
)
