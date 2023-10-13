python_sources(
    name="edx_sysadmin",
    dependencies=[
        "src/edx_sysadmin/settings:sysadmin_settings",
        "src/edx_sysadmin/management/commands:sysadmin_management_commands",
        "src/edx_sysadmin/migrations:sysadmin_migrations",
        "src/edx_sysadmin/api:sysadmin_api",
        "src/edx_sysadmin/utils:sysadmin_utils",
        "src/edx_sysadmin/templatetags:sysadmin_template_tags",
        ],
)

python_distribution(
    name="edx_sysadmin_package",
    dependencies=[
        ":edx_sysadmin",
        "src/edx_sysadmin/static/edx_sysadmin/js:sysadmin_js",
        "src/edx_sysadmin/static/edx_sysadmin/css:sysadmin_css",
        "src/edx_sysadmin/templates/edx_sysadmin:sysadmin_templates",
        "src/edx_sysadmin/conf/locale:sysadmin_locale",
    ],
    provides=setup_py(
        name="edx-sysadmin",
        version="0.2.3",
        description="An Open edX plugin to enable SysAdmin panel",
        license="BSD-3-Clause",
        author="MIT Office of Digital Learning",
        include_package_data=True,
        zip_safe=False,
        keywords="Python edx",
        entry_points={
            "lms.djangoapp": [
                "edx_sysadmin = edx_sysadmin.apps:EdxSysAdminConfig"
            ],
            "cms.djangoapp": [
                "edx_sysadmin = edx_sysadmin.apps:EdxSysAdminConfig"
            ],
        },
    ),
)

python_tests(
    name="tests",
)
