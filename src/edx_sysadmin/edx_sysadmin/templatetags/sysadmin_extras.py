"""
Provide extra utilities for templates
"""

from common.djangoapps.util.date_utils import DEFAULT_DATE_TIME_FORMAT, get_time_display
from django import template
from django.conf import settings
from pytz import UTC

register = template.Library()


@register.simple_tag
def change_time_display(cil_created):
    """Change time display to default settings format"""
    return get_time_display(
        cil_created.replace(tzinfo=UTC),
        DEFAULT_DATE_TIME_FORMAT,
        coerce_tz=settings.TIME_ZONE,
    )
