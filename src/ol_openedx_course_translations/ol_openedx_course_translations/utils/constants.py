"""Constants for translation synchronization."""

# Learner-facing frontend applications that require translation
LEARNER_FACING_APPS = [
    "frontend-app-learning",
    "frontend-app-learner-dashboard",
    "frontend-app-learner-record",
    "frontend-app-account",
    "frontend-app-profile",
    "frontend-app-authn",
    "frontend-app-catalog",
    "frontend-app-discussions",
    "frontend-component-header",
    "frontend-component-footer",
    "frontend-app-ora",
    "frontend-platform",
]

# Plural forms configuration for different languages
# Based on GNU gettext plural forms specification
# See: https://www.gnu.org/software/gettext/manual/html_node/Plural-forms.html
PLURAL_FORMS = {
    # Languages with no plural forms (nplurals=1)
    "ja": "nplurals=1; plural=0;",  # Japanese
    "ko": "nplurals=1; plural=0;",  # Korean
    "zh": "nplurals=1; plural=0;",  # Chinese (all variants)
    "th": "nplurals=1; plural=0;",  # Thai
    "vi": "nplurals=1; plural=0;",  # Vietnamese
    "id": "nplurals=1; plural=0;",  # Indonesian
    "ms": "nplurals=1; plural=0;",  # Malay
    "km": "nplurals=1; plural=0;",  # Khmer
    "bo": "nplurals=1; plural=0;",  # Tibetan
    # Languages with 2 plural forms: plural=(n != 1)
    "en": "nplurals=2; plural=(n != 1);",  # English
    "es": "nplurals=2; plural=(n != 1);",  # Spanish (all variants)
    "de": "nplurals=2; plural=(n != 1);",  # German
    "el": "nplurals=2; plural=(n != 1);",  # Greek
    "it": "nplurals=2; plural=(n != 1);",  # Italian
    "pt": "nplurals=2; plural=(n != 1);",  # Portuguese (all variants)
    "nl": "nplurals=2; plural=(n != 1);",  # Dutch
    "sv": "nplurals=2; plural=(n != 1);",  # Swedish
    "da": "nplurals=2; plural=(n != 1);",  # Danish
    "no": "nplurals=2; plural=(n != 1);",  # Norwegian
    "nb": "nplurals=2; plural=(n != 1);",  # Norwegian Bokmål
    "nn": "nplurals=2; plural=(n != 1);",  # Norwegian Nynorsk
    "fi": "nplurals=2; plural=(n != 1);",  # Finnish
    "is": "nplurals=2; plural=(n != 1);",  # Icelandic
    "et": "nplurals=2; plural=(n != 1);",  # Estonian
    "lv": "nplurals=2; plural=(n != 1);",  # Latvian
    "he": "nplurals=2; plural=(n != 1);",  # Hebrew
    "hi": "nplurals=2; plural=(n != 1);",  # Hindi
    "bn": "nplurals=2; plural=(n != 1);",  # Bengali
    "gu": "nplurals=2; plural=(n != 1);",  # Gujarati
    "kn": "nplurals=2; plural=(n != 1);",  # Kannada
    "ml": "nplurals=2; plural=(n != 1);",  # Malayalam
    "ta": "nplurals=2; plural=(n != 1);",  # Tamil
    "te": "nplurals=2; plural=(n != 1);",  # Telugu
    "or": "nplurals=2; plural=(n != 1);",  # Oriya
    "si": "nplurals=2; plural=(n != 1);",  # Sinhala
    "ne": "nplurals=2; plural=(n != 1);",  # Nepali
    "mr": "nplurals=2; plural=(n != 1);",  # Marathi
    "ur": "nplurals=2; plural=(n != 1);",  # Urdu
    "az": "nplurals=2; plural=(n != 1);",  # Azerbaijani
    "uz": "nplurals=2; plural=(n != 1);",  # Uzbek
    "kk": "nplurals=2; plural=(n != 1);",  # Kazakh
    "mn": "nplurals=2; plural=(n != 1);",  # Mongolian
    "sq": "nplurals=2; plural=(n != 1);",  # Albanian
    "eu": "nplurals=2; plural=(n != 1);",  # Basque
    "ca": "nplurals=2; plural=(n != 1);",  # Catalan
    "gl": "nplurals=2; plural=(n != 1);",  # Galician
    "tr": "nplurals=2; plural=(n != 1);",  # Turkish
    "af": "nplurals=2; plural=(n != 1);",  # Afrikaans
    "fil": "nplurals=2; plural=(n != 1);",  # Filipino
    # Languages with 2 plural forms: plural=(n > 1)
    "fr": "nplurals=2; plural=(n > 1);",  # French
    "br": "nplurals=2; plural=(n > 1);",  # Breton
    # Languages with 3 plural forms
    "pl": (
        "nplurals=3; plural=(n==1 ? 0 : n%10>=2 && n%10<=4 && "
        "(n%100<10 || n%100>=20) ? 1 : 2);"
    ),  # Polish
    "ru": (
        "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && "
        "(n%100<10 || n%100>=20) ? 1 : 2);"
    ),  # Russian
    "uk": (
        "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && "
        "(n%100<10 || n%100>=20) ? 1 : 2);"
    ),  # Ukrainian
    "be": (
        "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && "
        "(n%100<10 || n%100>=20) ? 1 : 2);"
    ),  # Belarusian
    "sr": (
        "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && "
        "(n%100<10 || n%100>=20) ? 1 : 2);"
    ),  # Serbian
    "hr": (
        "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && "
        "(n%100<10 || n%100>=20) ? 1 : 2);"
    ),  # Croatian
    "bs": (
        "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && "
        "(n%100<10 || n%100>=20) ? 1 : 2);"
    ),  # Bosnian
    "cs": "nplurals=3; plural=(n==1 ? 0 : (n>=2 && n<=4) ? 1 : 2);",  # Czech
    "sk": "nplurals=3; plural=(n==1 ? 0 : (n>=2 && n<=4) ? 1 : 2);",  # Slovak
    "lt": (
        "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && "
        "(n%100<10 || n%100>=20) ? 1 : 2);"
    ),  # Lithuanian
    "hy": "nplurals=3; plural=(n==1 ? 0 : n>=2 && n<=4 ? 1 : 2);",  # Armenian
    "ro": (
        "nplurals=3; plural=(n==1 ? 0 : (n==0 || (n%100 > 0 && n%100 < 20)) ? 1 : 2);"
    ),  # Romanian
    # Languages with 4 plural forms
    "cy": (
        "nplurals=4; plural=(n==1 ? 0 : n==2 ? 1 : (n==8 || n==11) ? 2 : 3);"
    ),  # Welsh
    "ga": "nplurals=4; plural=(n==1 ? 0 : n==2 ? 1 : (n>2 && n<7) ? 2 : 3);",  # Irish
    "gd": (
        "nplurals=4; plural=(n==1 || n==11) ? 0 : (n==2 || n==12) ? 1 : "
        "(n>2 && n<20) ? 2 : 3);"
    ),  # Scottish Gaelic
    "mt": (
        "nplurals=4; plural=(n==1 ? 0 : n==0 || (n%100>=2 && n%100<=10) ? 1 : "
        "(n%100>=11 && n%100<=19) ? 2 : 3);"
    ),  # Maltese
    # Languages with 6 plural forms
    "ar": (
        "nplurals=6; plural=(n==0 ? 0 : n==1 ? 1 : n==2 ? 2 : n%100>=3 && "
        "n%100<=10 ? 3 : n%100>=11 && n%100<=99 ? 4 : 5);"
    ),  # Arabic
    # Other languages
    "fa": "nplurals=2; plural=(n==0 || n==1 ? 0 : 1);",  # Persian/Farsi
    "hu": "nplurals=2; plural=(n != 1);",  # Hungarian
    "bg": "nplurals=2; plural=(n != 1);",  # Bulgarian
    "am": "nplurals=2; plural=(n > 1);",  # Amharic
}

# Default plural form fallback (English-style)
# Used when a language code is not found in PLURAL_FORMS
DEFAULT_PLURAL_FORM = "nplurals=2; plural=(n != 1);"

# Typo patterns to fix in translation files
TYPO_PATTERNS = [
    ("Serch", "Search"),
]

# Backend PO file names
BACKEND_PO_FILES = ["django.po", "djangojs.po"]

# PO file header metadata
PO_HEADER_PROJECT_VERSION = "0.1a"
PO_HEADER_BUGS_EMAIL = "openedx-translation@googlegroups.com"
PO_HEADER_POT_CREATION_DATE = "2023-06-13 08:00+0000"
PO_HEADER_MIME_VERSION = "1.0"
PO_HEADER_CONTENT_TYPE = "text/plain; charset=UTF-8"
PO_HEADER_CONTENT_TRANSFER_ENCODING = "8bit"
PO_HEADER_TRANSIFEX_TEAM_BASE_URL = "https://app.transifex.com/open-edx/teams/6205"

# File and directory names
TRANSLATION_FILE_NAMES = {
    "transifex_input": "transifex_input.json",
    "english": "en.json",
    "messages_dir": "messages",
    "i18n_dir": "i18n",
    "locale_dir": "locale",
    "lc_messages": "LC_MESSAGES",
    "conf_dir": "conf",
    "edx_platform": "edx-platform",
}

# JSON file formatting
DEFAULT_JSON_INDENT = 2

# Language code to human-readable name mapping
# Used in PO file headers for Language-Team field
LANGUAGE_MAPPING = {
    "ar": "Arabic",
    "de": "German",
    "el": "Greek",
    "es": "Spanish",
    "fr": "French",
    "hi": "Hindi",
    "id": "Indonesian",
    "ja": "Japanese",
    "kr": "Korean",
    "pt": "Portuguese",
    "ru": "Russian",
    "sq": "Albanian",
    "tr": "Turkish",
    "zh": "Chinese",
}

# Maximum number of retries for failed translation batches
MAX_RETRIES = 3

# Glossary parsing constants
EXPECTED_GLOSSARY_PARTS = 2  # English term and translation separated by "->"

# HTTP Status Codes
HTTP_OK = 200
HTTP_CREATED = 201
HTTP_NOT_FOUND = 404
HTTP_TOO_MANY_REQUESTS = 429
HTTP_UNPROCESSABLE_ENTITY = 422

# Error message length limit
MAX_ERROR_MESSAGE_LENGTH = 200
