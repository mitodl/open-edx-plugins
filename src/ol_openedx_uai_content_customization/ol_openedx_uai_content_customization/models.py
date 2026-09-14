"""Models for ol-openedx-uai-content-customization plugin."""

from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower

# Matches opaque_keys.edx.locator.Locator.ALLOWED_ID_CHARS: short_code is
# spliced directly into a course key's "course" (number) segment, so it must
# only contain characters CourseKey.from_string() will accept there.
short_code_validator = RegexValidator(
    regex=r"^[\w\-~.:]*$",
    message=(
        "short_code may contain only letters, numbers, and the characters "
        "_ - ~ . : (it is embedded directly into the generated course key)."
    ),
)


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
    short_code = models.CharField(
        max_length=10, blank=True, validators=[short_code_validator]
    )

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
