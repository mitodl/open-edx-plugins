"""
Ol Openedx LTI Utilities App Configuration
"""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginURLs
from openedx.core.djangoapps.plugins.constants import ProjectType


class LTIUtilitiesConfig(AppConfig):
    """
    Configuration class for Ol Openedx LTI Utilities
    """

    name = "ol_openedx_lti_utilities"

    plugin_app = {
        PluginURLs.CONFIG: {
            ProjectType.LMS: {
                PluginURLs.NAMESPACE: "",
                PluginURLs.REGEX: "^api/lti-user-fix/",
                PluginURLs.RELATIVE_PATH: "urls",
            }
        },
    }
