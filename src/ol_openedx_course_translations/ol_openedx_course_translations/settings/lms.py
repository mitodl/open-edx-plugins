# noqa: INP001

"""Settings to provide to edX"""

from ol_openedx_course_translations.settings.common import apply_common_settings


def plugin_settings(settings):
    """
    Populate lms settings
    """
    apply_common_settings(settings)
    settings.MIDDLEWARE.extend(
        ["ol_openedx_course_translations.middleware.CourseLanguageCookieMiddleware"]
    )
    VIDEO_TRANSCRIPT_LANGUAGE_FILTERS = {
        "org.openedx.learning.xblock.render.started.v1": {
            "pipeline": [
                "ol_openedx_course_translations.filters.AddDestLangForVideoBlock"
            ],
            "fail_silently": False,
        }
    }
    existing_filters = getattr(settings, "OPEN_EDX_FILTERS_CONFIG", {})

    # Merge pipeline lists instead of overwriting
    for filter_name, config in VIDEO_TRANSCRIPT_LANGUAGE_FILTERS.items():
        if filter_name not in existing_filters:
            existing_filters[filter_name] = config
        else:
            existing_filters[filter_name]["pipeline"].extend(config.get("pipeline", []))
            # do not override fail_silently
            if "fail_silently" in config:
                existing_filters[filter_name].setdefault(
                    "fail_silently", config["fail_silently"]
                )

    settings.OPEN_EDX_FILTERS_CONFIG = existing_filters
