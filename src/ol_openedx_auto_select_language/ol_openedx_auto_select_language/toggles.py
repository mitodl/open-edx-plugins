"""Toggles for ol_openedx_auto_select_language."""

from edx_toggles.toggles import WaffleFlag

# .. toggle_name: ol_openedx_auto_select_language.learner_language
# .. toggle_implementation: WaffleFlag
# .. toggle_default: False
# .. toggle_description: The learner's own language choice wins everywhere.
#   Course pages, staff pages and Studio stop switching or saving the language,
#   course-language lookups report the learner's language, and video subtitles
#   follow the learner's language before the course language.
LEARNER_LANGUAGE = WaffleFlag(
    "ol_openedx_auto_select_language.learner_language", __name__
)


def learner_language_enabled():
    """Return True when the learner's own language choice wins."""
    return LEARNER_LANGUAGE.is_enabled()
