"""Constants for course translation utilities."""

# LLM Provider names
PROVIDER_GEMINI = "gemini"
PROVIDER_MISTRAL = "mistral"
PROVIDER_OPENAI = "openai"

ENGLISH_LANGUAGE_CODE = "en"

# HTML/XML attribute translation policy
TRANSLATABLE_ATTRS_BASE = {
    "placeholder",
    "title",
    "aria-label",
    "alt",
    "label",
    "display_name",
}

# Open edX-specific: these are only translatable on <optioninput>
TRANSLATABLE_ATTRS_OPTIONINPUT_ONLY = {"options", "correct"}

# Never translate these (names), even if user-facing-ish in some contexts
NEVER_TRANSLATE_ATTRS = {
    "id",
    "class",
    "name",
    "href",
    "src",
    "role",
    "type",
    "url_name",
    "filename",
}

XML_FORMAT_ATTR = "format"

# Inline formatting tags: an element whose whole subtree is only these tags can
# be translated as ONE unit (its inner markup), so the LLM sees the full
# sentence and can reorder words for SOV/verb-final target languages.
INLINE_MARKUP_TAGS = {
    "a",
    "abbr",
    "b",
    "code",
    "em",
    "i",
    "mark",
    "small",
    "span",
    "strong",
    "sub",
    "sup",
    "u",
}
