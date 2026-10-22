"""Toggles for ol_openedx_auto_select_language."""

import re

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey, UsageKey
from openedx.core.djangoapps.waffle_utils import CourseWaffleFlag

# .. toggle_name: ol_openedx_auto_select_language.in_place_translations
# .. toggle_implementation: CourseWaffleFlag
# .. toggle_default: False
# .. toggle_description: In-place translations mode for a course: the learner's own
#   language choice wins and the course is shown in it. Course pages stop
#   switching or saving the language (Studio and staff pages stay English),
#   course-language lookups report the learner's language, video subtitles follow
#   the learner's language before the course language, and the course's
#   BlockTranslation rows are shown.
#   Pages outside a course follow the flag's global value.
IN_PLACE_TRANSLATIONS = CourseWaffleFlag(
    "ol_openedx_auto_select_language.in_place_translations", __name__
)


# Only new-style keys: the generic course key regex also matches paths like /a/b/c.
# Unit, sequence and Studio container URLs carry a usage key instead.
COURSE_KEY_IN_PATH = re.compile(r"(course|block)-v1:[^/?]+")


def course_key_from_path(path):
    """Return the course key found in a URL path, or None."""
    match = COURSE_KEY_IN_PATH.search(path or "")
    if not match:
        return None
    key = match.group(0)
    try:
        if key.startswith("block-v1:"):
            return UsageKey.from_string(key).course_key
        return CourseKey.from_string(key)
    except InvalidKeyError:
        return None


def in_place_translations_enabled(course_key=None):
    """Return True when the learner's own language choice wins for this course."""
    return IN_PLACE_TRANSLATIONS.is_enabled(course_key)
