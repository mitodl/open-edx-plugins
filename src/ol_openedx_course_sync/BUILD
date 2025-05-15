python_sources(
    name="ol_openedx_course_sync_source",
    dependencies=[
        "src/ol_openedx_course_sync/migrations:ol_openedx_course_sync_migrations",
    ],
)

python_distribution(
    name="ol_openedx_course_sync_package",
    dependencies=[":ol_openedx_course_sync_source"],
    provides=setup_py(
        name="ol-openedx-course-sync",
        version="0.1.0",
        description="An edX plugin to sync changes in a course to its target/child/rerun courses",
        license="BSD-3-Clause",
        author="MIT Office of Digital Learning",
        entry_points={
            "lms.djangoapp": [],
            "cms.djangoapp": [
                "ol_openedx_course_sync=ol_openedx_course_sync.apps:OLOpenEdxCourseSyncConfig",
            ],
        },
    ),
)
