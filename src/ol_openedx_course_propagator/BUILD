python_sources(
    name="ol_openedx_course_propagator_source",
    dependencies=[
        "//:external_dependencies#edx-opaque-keys",
        "//:external_dependencies#celery",
    ],
)

python_distribution(
    name="ol_openedx_course_propagator_package",
    dependencies=[":ol_openedx_course_propagator_source"],
    provides=setup_py(
        name="ol-openedx-course-propagator",
        version="0.1.0",
        description="An edX plugin to propagate changes in a course to its child courses",
        license="BSD-3-Clause",
        author="MIT Office of Digital Learning",
        include_package_data=True,
        zip_safe=False,
        keywords="Python edx",
        entry_points={
            "lms.djangoapp": [],
            "cms.djangoapp": [
                "ol_openedx_course_propagator = ol_openedx_course_propagator.apps:OLOpenEdxCoursePropagatorConfig",
            ],
        },
    ),
)
