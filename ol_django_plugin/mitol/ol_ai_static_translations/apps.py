"""AppConfig for mitol-django-ol_ai_static_translations."""

import os

from django.apps import AppConfig


class OlAiStaticTranslationsConfig(AppConfig):
    """Configuration for the ol_ai_static_translations Django application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "mitol.ol_ai_static_translations"
    label = "ol_ai_static_translations"
    verbose_name = "OL AI Static Translations"
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120
