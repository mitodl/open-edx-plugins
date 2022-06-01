python_sources(
    name="rapid_response_plugin_dependencies",
    dependencies=["src/ol_openedx_rapid_response_reports/settings:rapid_response_settings"],
)

resources(
  name="rapid_response_plugin_templates",
  sources=[],
  dependencies=["src/ol_openedx_rapid_response_reports/templates:rapid_response_templates"]
)

python_distribution(
    name="rapid_response_plugin_dist",
    dependencies=[":rapid_response_plugin_dependencies", ":rapid_response_plugin_templates"],
    provides=setup_py(
        name="ol-openedx-rapid-response-reports",
        version="0.2.1",
        description="An Open edX plugin to add rapid response reports support",
        license="BSD-3-Clause",
        entry_points={
            "lms.djangoapp": [
                "ol_openedx_rapid_response_reports = ol_openedx_rapid_response_reports.app:RapidResponsePluginConfig"
            ],
            "cms.djangoapp": [],
        },
    ),
)
