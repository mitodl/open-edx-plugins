python_sources(
    name="git_auto_export",
    dependencies=[
        "src/ol_openedx_git_auto_export/settings:git_auto_export_settings",
        "//:external_dependencies#edx-opaque-keys",
        "//:external_dependencies#celery",
    ],
)

python_distribution(
    name="edx_git_auto_export",
    dependencies=[":git_auto_export"],
    provides=setup_py(
        name="ol-openedx-git-auto-export",
        version="0.4.1",
        license="BSD-3-Clause",
        description="A plugin that auto saves the course OLX to git when an author publishes it",
        entry_points={
            "cms.djangoapp": [
                "ol_openedx_git_auto_export=ol_openedx_git_auto_export.app:GitAutoExportConfig"
            ],
            "lms.djangoapp": [],
        },
    ),
)
