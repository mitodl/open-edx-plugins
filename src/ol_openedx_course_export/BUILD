python_sources(
    name="course_export",
    dependencies=["src/ol_openedx_course_export/settings:course_export_settings"],
)

python_distribution(
    name="course_export_package",
    dependencies=[":course_export"],
    provides=setup_py(
        name="ol-openedx-course-export",
        version="0.1.1",
        description="An Open edX plugin to add API for course export to s3",
        entry_points={
            "lms.djangoapp": [],
            "cms.djangoapp": [
                "ol_openedx_course_export = ol_openedx_course_export.app:CourseExportConfig"
            ],
        },
    ),
)
