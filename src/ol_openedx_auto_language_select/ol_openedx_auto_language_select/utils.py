"""
Utils for ol_openedx_auto_language_select.
"""

import re


class LanguageCode:
    """
    Utility class for handling language code conversions between
    Django/Open edX style and BCP47.
    """

    def __init__(self, lang_code):
        self.lang_code = lang_code

    def to_bcp47(self) -> str:
        """
        Convert Django / Open edX style language codes to BCP47.

        Examples:
            zh_HANS     -> zh-Hans
            zh_HANT     -> zh-Hant
            zh_HANS_CN  -> zh-Hans-CN
            en_US       -> en-US
            es_419      -> es-419
            pt_br       -> pt-BR
        """
        if not self.lang_code:
            return self.lang_code

        parts = self.lang_code.replace("_", "-").split("-")
        result = []
        for idx, part in enumerate(parts):
            if idx == 0:
                # Language
                result.append(part.lower())

            elif re.fullmatch(r"[A-Za-z]{4}", part):
                # Script (Hans, Hant, Latn, Cyrl, etc.)
                result.append(part.title())

            elif re.fullmatch(r"[A-Za-z]{2}", part):
                # Region i.e US, PK, CN
                result.append(part.upper())

            elif re.fullmatch(r"\d{3}", part):
                # Numeric region (419)
                result.append(part)

            else:
                # Variants/extensions
                result.append(part.lower())

        return "-".join(result)

    def to_django(self) -> str:
        """
        Convert BCP47 language tags to Django / Open edX style.

        Examples:
            zh-Hans     -> zh_HANS
            zh-Hant     -> zh_HANT
            zh-Hans-CN  -> zh_HANS_CN
            en-US       -> en_US
            es-419      -> es_419
            pt-BR       -> pt_BR
        """
        if not self.lang_code:
            return self.lang_code

        parts = self.lang_code.replace("_", "-").split("-")
        result = []

        for idx, part in enumerate(parts):
            if idx == 0:
                # Language
                result.append(part.lower())

            elif re.fullmatch(r"[A-Za-z]{4}", part):
                # Script
                result.append(part.upper())

            elif re.fullmatch(r"[A-Za-z]{2}", part):
                # Region
                result.append(part.upper())

            elif re.fullmatch(r"\d{3}", part):
                # Numeric region
                result.append(part)

            else:
                # Variants/extensions
                result.append(part.lower())

        return "_".join(result)
