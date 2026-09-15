"""Models for ol-openedx-uai-content-customization plugin."""

from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower
from opaque_keys.edx.locator import Locator

# short_code is spliced directly into a course key's "course" (number)
# segment, so it must only contain characters CourseKey.from_string() will
# accept there — reuse the library's own allowed-character set rather than
# hand-copying it, so this stays in sync if opaque_keys ever changes it.
short_code_validator = RegexValidator(
    # \A/\Z (not ^/$) so a trailing newline can't sneak past the anchors —
    # `$` matches just before a trailing "\n" even without re.MULTILINE.
    regex=rf"\A{Locator.ALLOWED_ID_CHARS}*\Z",
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
