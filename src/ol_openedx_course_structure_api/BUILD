python_sources(
    name="course_structure_api",
    dependencies=["src/ol_openedx_course_structure_api/settings:course_structure_api_settings"],
)

python_distribution(
    name="course_structure_api_package",
    dependencies=[":course_structure_api"],
    provides=setup_py(
        name="ol-openedx-course-structure-api",
        version="0.1.0",
        description="An Open edX plugin to add API for course structure",
        license="BSD-3-Clause",
        entry_points={
            "lms.djangoapp": [
                 "ol_openedx_course_structure_api = ol_openedx_course_structure_api.app.CourseStructureAPIConfig"
            ],
            "cms.djangoapp": [],
        },
    ),
)
