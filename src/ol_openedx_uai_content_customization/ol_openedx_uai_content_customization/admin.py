"""Django admin configuration for ol-openedx-uai-content-customization plugin."""

from django.contrib import admin

from ol_openedx_uai_content_customization.models import Industry


@admin.register(Industry)
class IndustryAdmin(admin.ModelAdmin):
    """Admin interface for the Industry model."""

    list_display = ("id", "name", "short_code")
    search_fields = ("name", "short_code")
