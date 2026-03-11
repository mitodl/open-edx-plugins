"""Constants for course translations."""

# LLM Provider names
PROVIDER_DEEPL = "deepl"
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
