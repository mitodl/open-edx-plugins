"""
App configuration for ol-openedx-course-propagator plugin
"""

from django.apps import AppConfig


class OLOpenEdxCoursePropagatorConfig(AppConfig):
    name = "ol_openedx_course_propagator"
    verbose_name = "Open edX Course Propagator"

    plugin_app = {
        PluginSignals.CONFIG: {
            ProjectType.CMS: {
                PluginSignals.RECEIVERS: [
                    {
                        PluginSignals.RECEIVER_FUNC_NAME: "listen_for_course_publish",
                        PluginSignals.SIGNAL_PATH: "xmodule.modulestore.django.COURSE_PUBLISHED",  # noqa: E501
                        PluginSignals.DISPATCH_UID: "ol_openedx_course_propagator.signals.listen_for_course_publish",  # noqa: E501
                    }
                ],
            },
        },
    }
