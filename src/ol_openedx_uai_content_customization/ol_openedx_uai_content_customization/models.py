"""Models for ol-openedx-uai-content-customization plugin."""

from django.db import models
from django.db.models.functions import Lower


class Industry(models.Model):
    """
    An industry variant a UAI course can be customized for.

    ``short_code`` is used as the course-key suffix segment (e.g. "HC" for
    Healthcare). The "Original" industry - meaning no industry-specific
    variant is applied, only the duration suffix - is represented by a
    blank short_code. Both ``name`` and ``short_code`` are unique
    case-insensitively.
    """

    name = models.CharField(max_length=255)
    short_code = models.CharField(max_length=10, blank=True)

    class Meta:
        """Meta options for Industry."""

        app_label = "ol_openedx_uai_content_customization"
        verbose_name_plural = "Industries"
        constraints = [
            models.UniqueConstraint(Lower("name"), name="unique_industry_name_ci"),
            models.UniqueConstraint(
                Lower("short_code"), name="unique_industry_short_code_ci"
            ),
        ]

    def __str__(self):
        """Return a string representation of the industry."""
        return self.name
