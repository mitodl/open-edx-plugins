"""Translation synchronization module for syncing and managing translation files."""

import json
import logging
from collections import OrderedDict
from pathlib import Path
from typing import Any

import polib  # type: ignore[import-untyped]

from ol_openedx_course_translations.utils.constants import (
    BACKEND_PO_FILES,
    DEFAULT_JSON_INDENT,
    DEFAULT_PLURAL_FORM,
    EXPECTED_GLOSSARY_PARTS,
    LANGUAGE_MAPPING,
    LEARNER_FACING_APPS,
    PLURAL_FORMS,
    PO_HEADER_BUGS_EMAIL,
    PO_HEADER_CONTENT_TRANSFER_ENCODING,
    PO_HEADER_CONTENT_TYPE,
    PO_HEADER_MIME_VERSION,
    PO_HEADER_POT_CREATION_DATE,
    PO_HEADER_PROJECT_VERSION,
    PO_HEADER_TRANSIFEX_TEAM_BASE_URL,
    TRANSLATION_FILE_NAMES,
    TYPO_PATTERNS,
)

logger = logging.getLogger(__name__)

# Constants for string truncation in logging
MAX_LOG_STRING_LENGTH = 50


def load_json_file(file_path: Path) -> dict:
    """Load a JSON translation file."""
    if not file_path.exists():
        return {}
    try:
        with file_path.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        msg = f"Error parsing JSON file {file_path}: {e}"
        raise ValueError(msg) from e


def save_json_file(file_path: Path, data: dict, indent: int = DEFAULT_JSON_INDENT):
    """Save a JSON translation file with proper formatting."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
        f.write("\n")


def find_typo_mappings(data: dict) -> list[tuple[str, str]]:
    """Find typo keys and their correct counterparts."""
    mappings = []

    for typo, correct in TYPO_PATTERNS:
        typo_keys = [k for k in data if typo in k]
        for typo_key in typo_keys:
            correct_key = typo_key.replace(typo, correct)
            if correct_key in data:
                mappings.append((typo_key, correct_key))

    return mappings


def sync_or_create_json_file(en_file: Path, target_file: Path) -> dict:
    """
    Sync or create a JSON translation file.
    Returns dict with stats:
        {'action': 'created'|'synced'|'skipped', 'added': int,
         'fixed': int, 'removed': int}
    """
    try:
        en_data = load_json_file(en_file)
    except ValueError:
        return {
            "action": "skipped",
            "added": 0,
            "fixed": 0,
            "removed": 0,
            "error": "English file not readable",
        }

    if not en_data:
        return {
            "action": "skipped",
            "added": 0,
            "fixed": 0,
            "removed": 0,
            "error": "English file is empty",
        }

    target_data = load_json_file(target_file) if target_file.exists() else {}
    file_exists = target_file.exists()

    stats = {
        "action": "created" if not file_exists else "synced",
        "added": 0,
        "fixed": 0,
        "removed": 0,
    }

    if file_exists:
        ordered_data = OrderedDict(target_data)

        typo_mappings = find_typo_mappings(ordered_data)
        for typo_key, correct_key in typo_mappings:
            typo_value = ordered_data.get(typo_key, "")
            correct_value = ordered_data.get(correct_key, "")

            if not correct_value and typo_value:
                ordered_data[correct_key] = typo_value
                # Type assertion: stats["fixed"] is always int
                stats["fixed"] = int(stats["fixed"]) + 1

            if typo_key in ordered_data:
                del ordered_data[typo_key]
                # Type assertion: stats["removed"] is always int
                stats["removed"] = int(stats["removed"]) + 1

        for key in en_data:
            if key not in ordered_data:
                ordered_data[key] = ""
                # Type assertion: stats["added"] is always int
                stats["added"] = int(stats["added"]) + 1

        target_data = dict(ordered_data)
    else:
        target_data = dict.fromkeys(en_data, "")
        stats["added"] = len(en_data)

    save_json_file(target_file, target_data)

    return stats


def _get_base_lang(lang_code: str) -> str:
    """Extract base language code from locale code (e.g., 'es_ES' -> 'es')."""
    return lang_code.split("_")[0] if "_" in lang_code else lang_code


def _get_plural_form(lang_code: str) -> str:
    """Get plural form string for a language code."""
    base_lang = _get_base_lang(lang_code)
    return PLURAL_FORMS.get(base_lang, DEFAULT_PLURAL_FORM)


def create_po_file_header(lang_code: str, iso_code: str | None = None) -> str:
    """Create PO file header for a language."""
    if iso_code is None:
        iso_code = lang_code

    base_lang = _get_base_lang(lang_code)
    plural = _get_plural_form(lang_code)
    lang_name = LANGUAGE_MAPPING.get(lang_code, lang_code)

    return f"""msgid ""
msgstr ""
"Project-Id-Version: {PO_HEADER_PROJECT_VERSION}\\n"
"Report-Msgid-Bugs-To: {PO_HEADER_BUGS_EMAIL}\\n"
"POT-Creation-Date: {PO_HEADER_POT_CREATION_DATE}\\n"
"PO-Revision-Date: 2025-01-01 00:00+0000\\n"
"Last-Translator: \\n"
"Language-Team: {lang_name} ({PO_HEADER_TRANSIFEX_TEAM_BASE_URL}/{base_lang}/)\\n"
"MIME-Version: {PO_HEADER_MIME_VERSION}\\n"
"Content-Type: {PO_HEADER_CONTENT_TYPE}\\n"
"Content-Transfer-Encoding: {PO_HEADER_CONTENT_TRANSFER_ENCODING}\\n"
"Language: {iso_code}\\n"
"Plural-Forms: {plural}\\n"

"""


def parse_po_file(po_file: Path) -> dict[str, str]:
    """
    Parse a PO file and extract msgid -> msgstr mappings.
    For plural forms, uses msgid as the key
    (msgid_plural entries are handled separately).
    Uses polib if available, falls back to manual parsing.
    """
    if not po_file.exists():
        return {}

    po = polib.pofile(str(po_file))
    entries = {}
    for entry in po:
        if entry.msgid:  # Skip empty header msgid
            # For plural entries, use msgid as key
            entries[entry.msgid] = entry.msgstr or ""
    return entries


def parse_po_file_with_metadata(po_file: Path) -> dict[str, dict]:
    """
    Parse a PO file and extract msgid -> metadata mappings.
    Returns dict with structure:
        {msgid: {'msgstr': str, 'msgid_plural': str, 'msgstr_plural': dict,
                 'locations': List[str], 'flags': List[str], 'is_plural': bool}}
    Uses polib if available, falls back to manual parsing.
    """
    if not po_file.exists():
        return {}

    po = polib.pofile(str(po_file))
    entries = {}
    for entry in po:
        if entry.msgid:  # Skip empty header msgid
            locations = [
                f"{occ[0]}:{occ[1]}" if len(occ) > 1 else occ[0]
                for occ in entry.occurrences
            ]

            entry_data = {
                "msgstr": entry.msgstr or "",
                "locations": locations,
                "flags": entry.flags,  # List of flags like ['python-format']
                "is_plural": entry.msgid_plural is not None,
            }
            if entry.msgid_plural:
                entry_data["msgid_plural"] = entry.msgid_plural
                # Convert msgstr_plural dict to simple dict
                entry_data["msgstr_plural"] = {
                    i: entry.msgstr_plural.get(i, "")
                    for i in range(len(entry.msgstr_plural))
                }
            entries[entry.msgid] = entry_data
    return entries


def _create_po_entry_from_en(entry: polib.POEntry) -> polib.POEntry:
    """Create a new PO entry from an English entry with empty translation."""
    new_entry = polib.POEntry(
        msgid=entry.msgid,
        msgid_plural=entry.msgid_plural,
        occurrences=entry.occurrences,
        flags=entry.flags,
    )
    if entry.msgid_plural:
        # Initialize plural forms (at least 2)
        num_forms = max(2, len(entry.msgstr_plural) if entry.msgstr_plural else 2)
        new_entry.msgstr_plural = dict.fromkeys(range(num_forms), "")
    else:
        new_entry.msgstr = ""
    return new_entry


def _sync_existing_po_file(
    en_po: polib.POFile, target_po: polib.POFile, target_file: Path
) -> int:
    """Sync existing PO file by adding missing entries. Returns count added."""
    # Create a set of existing entries (msgid + msgid_plural for plural entries)
    existing_entries = set()
    for entry in target_po:
        if entry.msgid:
            key = (entry.msgid, entry.msgid_plural if entry.msgid_plural else None)
            existing_entries.add(key)

    # Add missing entries from English file
    added_count = 0
    for entry in en_po:
        if not entry.msgid:  # Skip header
            continue

        entry_key = (entry.msgid, entry.msgid_plural if entry.msgid_plural else None)
        if entry_key not in existing_entries:
            new_entry = _create_po_entry_from_en(entry)
            target_po.append(new_entry)
            added_count += 1

    if added_count > 0:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_po.save(str(target_file))

    return added_count


def _create_new_po_file(
    en_po: polib.POFile, target_file: Path, lang_code: str, iso_code: str | None
) -> int:
    """Create a new PO file with all entries from English. Returns count added."""
    target_po = polib.POFile()

    # Set metadata - preserve important fields from English file
    target_po.metadata = en_po.metadata.copy()
    target_po.metadata["Language"] = iso_code or lang_code

    # Ensure Plural-Forms is set correctly for the target language
    if "Plural-Forms" not in target_po.metadata:
        target_po.metadata["Plural-Forms"] = _get_plural_form(lang_code)

    # Copy all entries with empty translations
    added_count = 0
    for entry in en_po:
        if not entry.msgid:  # Skip header
            continue

        new_entry = _create_po_entry_from_en(entry)
        target_po.append(new_entry)
        added_count += 1

    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_po.save(str(target_file))
    return added_count


def sync_or_create_po_file(
    en_file: Path, target_file: Path, lang_code: str, iso_code: str | None = None
) -> dict:
    """
    Sync or create a PO file, preserving location comments and format flags.
    Returns dict with stats: {'action': 'created'|'synced'|'skipped', 'added': int}
    Uses polib if available for robust PO file handling.
    """
    if not en_file.exists():
        return {"action": "skipped", "added": 0, "error": "English file does not exist"}

    file_exists = target_file.exists()
    stats = {"action": "created" if not file_exists else "synced", "added": 0}

    # Use polib for robust PO file handling
    en_po = polib.pofile(str(en_file))

    if not en_po:
        return {"action": "skipped", "added": 0, "error": "English file has no entries"}

    if file_exists:
        # File exists: sync entries
        target_po = polib.pofile(str(target_file))
        stats["added"] = _sync_existing_po_file(en_po, target_po, target_file)
    else:
        # File doesn't exist: create new with all entries from English
        stats["added"] = _create_new_po_file(en_po, target_file, lang_code, iso_code)

    return stats


def _extract_empty_keys_from_frontend(base_dir: Path, iso_code: str) -> list[dict]:
    """Extract empty translation keys from frontend JSON files."""
    logger.debug("Extracting empty keys from frontend apps for language: %s", iso_code)
    """Extract empty keys from frontend JSON files."""
    empty_keys = []

    for app in LEARNER_FACING_APPS:
        target_file = (
            base_dir
            / app
            / "src"
            / TRANSLATION_FILE_NAMES["i18n_dir"]
            / TRANSLATION_FILE_NAMES["messages_dir"]
            / f"{iso_code}.json"
        )
        en_file = (
            base_dir
            / app
            / "src"
            / TRANSLATION_FILE_NAMES["i18n_dir"]
            / TRANSLATION_FILE_NAMES["transifex_input"]
        )
        if not en_file.exists():
            en_file = (
                base_dir
                / app
                / "src"
                / TRANSLATION_FILE_NAMES["i18n_dir"]
                / TRANSLATION_FILE_NAMES["messages_dir"]
                / TRANSLATION_FILE_NAMES["english"]
            )

        if not target_file.exists() or not en_file.exists():
            logger.debug(
                "Skipping %s: target file or English file missing (target: %s, en: %s)",
                app,
                target_file.exists(),
                en_file.exists(),
            )
            continue

        try:
            target_data = load_json_file(target_file)
            en_data = load_json_file(en_file)
            logger.debug(
                "Processing %s: found %d keys in English file", app, len(en_data)
            )

            for key in en_data:
                target_value = target_data.get(key, "")
                if not target_value or (
                    isinstance(target_value, str) and not target_value.strip()
                ):
                    english_value = en_data[key]
                    # Skip non-string values (numbers, booleans, objects, arrays)
                    # These shouldn't be translated as they would break JSON structure
                    if not isinstance(english_value, str):
                        logger.debug(
                            "Skipping non-string value for key '%s' in %s: %s "
                            "(type: %s). Only string values are translatable.",
                            key,
                            app,
                            english_value,
                            type(english_value).__name__,
                        )
                        continue
                    # Check if English value is already in ICU MessageFormat
                    is_icu_plural = (
                        isinstance(english_value, str) and ", plural," in english_value
                    )

                    empty_keys.append(
                        {
                            "app": app,
                            "key": key,
                            "english": english_value,
                            "translation": "",
                            "file_type": "json",
                            "file_path": str(target_file.resolve()),
                            "is_plural": is_icu_plural,
                        }
                    )
            logger.debug("Extracted %d empty key(s) from %s", len(empty_keys), app)
        except (OSError, ValueError, json.JSONDecodeError) as e:
            logger.warning(
                "Skipping %s due to error loading translation files: %s", app, e
            )
            continue

    logger.info(
        "Extracted %d total empty key(s) from frontend apps for language: %s",
        len(empty_keys),
        iso_code,
    )
    return empty_keys


def _is_po_entry_empty(
    entry: polib.POEntry, target_entry: polib.POEntry | None
) -> bool:
    """Check if a PO entry is empty or missing."""
    if target_entry is None:
        return True

    if entry.msgid_plural:
        # Plural entry - check if plural forms are empty
        return any(
            not target_entry.msgstr_plural.get(i, "").strip()
            for i in range(len(target_entry.msgstr_plural))
        )

    # Singular entry - check if empty
    return not target_entry.msgstr or not target_entry.msgstr.strip()


def _extract_empty_keys_from_backend(base_dir: Path, backend_locale: str) -> list[dict]:
    """Extract empty keys from backend PO files."""
    empty_keys = []
    locale_dir = (
        base_dir
        / TRANSLATION_FILE_NAMES["edx_platform"]
        / TRANSLATION_FILE_NAMES["conf_dir"]
        / TRANSLATION_FILE_NAMES["locale_dir"]
        / backend_locale
        / TRANSLATION_FILE_NAMES["lc_messages"]
    )

    for po_file_name in BACKEND_PO_FILES:
        target_file = locale_dir / po_file_name
        en_file = (
            base_dir
            / TRANSLATION_FILE_NAMES["edx_platform"]
            / TRANSLATION_FILE_NAMES["conf_dir"]
            / TRANSLATION_FILE_NAMES["locale_dir"]
            / "en"
            / TRANSLATION_FILE_NAMES["lc_messages"]
            / po_file_name
        )

        if not target_file.exists() or not en_file.exists():
            continue

        try:
            target_po = polib.pofile(str(target_file))
            en_po = polib.pofile(str(en_file))

            target_entries_dict = {
                entry.msgid: entry for entry in target_po if entry.msgid
            }

            for entry in en_po:
                if not entry.msgid:  # Skip header
                    continue

                target_entry = target_entries_dict.get(entry.msgid)
                if _is_po_entry_empty(entry, target_entry):
                    empty_keys.append(
                        {
                            "app": "edx-platform",
                            "key": entry.msgid,
                            "english": entry.msgid,
                            "translation": "",
                            "file_type": "po",
                            "file_path": str(target_file.resolve()),
                            "po_file": po_file_name,
                            "is_plural": entry.msgid_plural is not None,
                            "msgid_plural": entry.msgid_plural
                            if entry.msgid_plural
                            else None,
                        }
                    )
        except (OSError, polib.POFileError, ValueError) as e:
            logger.warning(
                "Skipping %s due to error loading PO file: %s", target_file, e
            )
            continue

    return empty_keys


def extract_empty_keys(
    base_dir: Path,
    lang_code: str,
    iso_code: str | None = None,
    *,
    skip_backend: bool = False,
) -> list[dict]:
    """
    Extract all empty translation keys for a language.
    Returns list of dicts with:
        {'app': str, 'key': str, 'english': str, 'file_type': 'json'|'po'}
    """
    if iso_code is None:
        iso_code = lang_code

    empty_keys = _extract_empty_keys_from_frontend(base_dir, iso_code)

    if not skip_backend:
        backend_locale = iso_code if iso_code and iso_code != lang_code else lang_code
        empty_keys.extend(_extract_empty_keys_from_backend(base_dir, backend_locale))

    return empty_keys


def apply_json_translations(file_path: Path, translations: dict[str, str]) -> int:
    """
    Apply translations to a JSON file.
    Returns number of translations applied.
    """
    data = load_json_file(file_path)
    applied = 0
    skipped = 0

    for key, translation in translations.items():
        if key in data:
            # Check if the value is empty (empty string, whitespace only, or None)
            current_value = data[key]
            if not current_value or (
                isinstance(current_value, str) and not current_value.strip()
            ):
                data[key] = translation
                applied += 1
                logger.debug(
                    "Applied translation for key '%s' in %s", key, file_path.name
                )
            else:
                skipped += 1
                logger.debug(
                    "Skipped key '%s' in %s (already has value: %s)",
                    key,
                    file_path.name,
                    current_value[:50]
                    if isinstance(current_value, str)
                    else current_value,
                )
        else:
            skipped += 1
            logger.debug(
                "Skipped key '%s' in %s (key not found in target file)",
                key,
                file_path.name,
            )

    if applied > 0:
        save_json_file(file_path, data)
        logger.info(
            "Applied %d translation(s) to %s (%d skipped)",
            applied,
            file_path.name,
            skipped,
        )
    elif skipped > 0:
        logger.debug(
            "No translations applied to %s (%d keys skipped - already have values)",
            file_path.name,
            skipped,
        )

    return applied


def load_glossary(glossary_path: Path, _lang_code: str = "") -> dict[str, Any]:
    """
    Load glossary for a language from a text file.
    Parses text format with term mappings like: - 'english term' -> 'translation'
    Returns dict mapping English -> Translation (string or dict for plural forms).

    Args:
        glossary_path: Path to the glossary text file.
        _lang_code: Language code (currently unused, kept for API compatibility).

    Returns:
        Dictionary mapping English terms to translations. Translations can be:
        - Strings for singular terms
        - Dicts with 'singular' and 'plural' keys for plural forms

    Text file format:
    # Comments and headers
    ## TERM MAPPINGS
    - 'english term' -> 'translation'
    - 'another term' -> 'another translation'

    Example:
    - 'accuracy' -> 'الدقة'
    - 'activation function' -> 'دالّة التفعيل'
    """
    if not glossary_path.exists():
        return {}

    glossary = {}

    try:
        with glossary_path.open(encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()

                # Skip empty lines, comments, and headers
                if not line or line.startswith("#"):
                    continue

                # Parse lines like: - 'english term' -> 'translation'
                if line.startswith("- ") and "->" in line:
                    # Extract the mapping
                    # Format: - 'english term' -> 'translation'
                    mapping_line = line[2:].strip()  # Remove leading '- '
                    parts = mapping_line.split("->", 1)

                    if len(parts) == EXPECTED_GLOSSARY_PARTS:
                        english_term = parts[0].strip().strip("'\"")
                        translation = parts[1].strip().strip("'\"")

                        if english_term and translation:
                            glossary[english_term] = translation
    except (OSError, UnicodeDecodeError):
        # Log specific file-related errors but return empty dict to allow continuation
        # In a library function, we can't use stdout, so we just return empty dict
        # The caller can handle logging if needed
        return {}
    except (ValueError, AttributeError, IndexError):
        # Catch parsing errors and other unexpected errors
        return {}
    else:
        return glossary


def match_glossary_term(
    text: str, glossary: dict[str, Any] | None, *, exact_match: bool = True
) -> Any | None:
    """
    Match text against glossary terms.
    Returns translation (string or dict with 'singular'/'plural') if match found,
    None otherwise.
    Supports both simple format ("term": "translation") and plural format
    ("term": {"singular": "...", "plural": "..."}).

    Args:
        text: The text to match against glossary terms.
        glossary: Dictionary mapping English terms to translations, or None.
        exact_match: If True, only exact matches are returned.
            If False, case-insensitive and partial matches are allowed.

    Returns:
        Translation string/dict if match found, None otherwise.
    """
    if not glossary:
        return None

    if text in glossary:
        # Return as-is: string for singular, dict for plural
        return glossary[text]

    if not exact_match:
        text_lower = text.lower().strip()
        for term, translation in glossary.items():
            if term.lower().strip() == text_lower:
                return translation

        for term, translation in glossary.items():
            if term.lower() in text_lower or text_lower in term.lower():
                return translation

    return None


def _apply_plural_dict_translation(
    entry: polib.POEntry, translation: dict[str, str]
) -> bool:
    """Apply plural translation from dict. Returns True if applied."""
    plural_applied = False
    # Apply singular to form 0
    if not entry.msgstr_plural.get(0, "").strip():
        entry.msgstr_plural[0] = translation["singular"]
        plural_applied = True
    # Apply plural to all remaining empty forms (for languages with >2 forms)
    for i in range(1, len(entry.msgstr_plural)):
        if not entry.msgstr_plural.get(i, "").strip():
            entry.msgstr_plural[i] = translation["plural"]
            plural_applied = True
    return plural_applied


def _apply_plural_string_translation(entry: polib.POEntry, translation: str) -> bool:
    """Apply plural translation from string. Returns True if applied."""
    plural_applied = False
    for i in range(len(entry.msgstr_plural)):
        if not entry.msgstr_plural.get(i, "").strip():
            entry.msgstr_plural[i] = translation
            plural_applied = True
    return plural_applied


def _apply_translation_to_entry(entry: polib.POEntry, translation: Any) -> bool:
    """
    Apply translation to a PO entry. Returns True if translation was applied.

    Args:
        entry: The PO entry to apply translation to.
        translation: Translation value (string or dict with 'singular'/'plural').

    Returns:
        True if translation was applied, False otherwise.
    """
    if entry.msgid_plural:
        # Plural entry
        if (
            isinstance(translation, dict)
            and "singular" in translation
            and "plural" in translation
        ):
            return _apply_plural_dict_translation(entry, translation)
        if (
            isinstance(translation, str)
            and translation
            and _apply_plural_string_translation(entry, translation)
        ):
            return True
    # Singular entry - translation should be a string
    elif (
        isinstance(translation, str)
        and translation
        and (not entry.msgstr or not entry.msgstr.strip())
    ):
        entry.msgstr = translation
        return True
    return False


def apply_po_translations(file_path: Path, translations: dict[str, Any]) -> int:
    """
    Apply translations to a PO file. Returns number of translations applied.
    Handles both singular and plural forms.
    For plural forms, translations dict can contain:
    - Dict with 'singular' and 'plural' keys: {"singular": "...", "plural": "..."}
    - String: applies same translation to all plural forms
    """
    po = polib.pofile(str(file_path))
    applied = 0
    skipped = 0

    for entry in po:
        if not entry.msgid:
            continue

        if entry.msgid in translations:
            translation = translations[entry.msgid]
            if _apply_translation_to_entry(entry, translation):
                applied += 1
                logger.debug(
                    "Applied translation for msgid '%s' in %s",
                    (
                        entry.msgid[:MAX_LOG_STRING_LENGTH] + "..."
                        if len(entry.msgid) > MAX_LOG_STRING_LENGTH
                        else entry.msgid
                    ),
                    file_path.name,
                )
            else:
                skipped += 1
                logger.debug(
                    "Skipped msgid '%s' in %s (already has translation)",
                    (
                        entry.msgid[:MAX_LOG_STRING_LENGTH] + "..."
                        if len(entry.msgid) > MAX_LOG_STRING_LENGTH
                        else entry.msgid
                    ),
                    file_path.name,
                )
        else:
            skipped += 1

    if applied > 0:
        po.save(str(file_path))
        logger.info(
            "Applied %d translation(s) to %s (%d skipped)",
            applied,
            file_path.name,
            skipped,
        )
    elif skipped > 0:
        logger.debug(
            "No translations applied to %s (%d entries skipped - "
            "already have translations)",
            file_path.name,
            skipped,
        )

    return applied


def _sync_frontend_translations(base_dir: Path, iso_code: str) -> dict[str, int]:
    """Sync frontend translation files. Returns stats."""
    frontend_stats = {"added": 0, "fixed": 0, "removed": 0, "created": 0, "synced": 0}

    for app in LEARNER_FACING_APPS:
        app_dir = base_dir / app / "src" / TRANSLATION_FILE_NAMES["i18n_dir"]
        messages_dir = app_dir / TRANSLATION_FILE_NAMES["messages_dir"]

        en_file = app_dir / TRANSLATION_FILE_NAMES["transifex_input"]
        if not en_file.exists():
            en_file = messages_dir / TRANSLATION_FILE_NAMES["english"]

        target_file = messages_dir / f"{iso_code}.json"

        if not en_file.exists():
            continue

        try:
            stats = sync_or_create_json_file(en_file, target_file)
            if stats["action"] == "created":
                frontend_stats["created"] += 1
            elif stats["action"] == "synced":
                frontend_stats["synced"] += 1

            frontend_stats["added"] += stats.get("added", 0)
            frontend_stats["fixed"] += stats.get("fixed", 0)
            frontend_stats["removed"] += stats.get("removed", 0)
        except (OSError, ValueError, json.JSONDecodeError) as e:
            logger.warning(
                "Skipping %s due to error syncing translation file: %s", app, e
            )
            continue

    return frontend_stats


def _sync_backend_translations(
    base_dir: Path, lang_code: str, iso_code: str
) -> dict[str, int]:
    """Sync backend translation files. Returns stats."""
    backend_stats = {"added": 0}
    backend_locale = iso_code if iso_code and iso_code != lang_code else lang_code
    locale_dir = (
        base_dir
        / TRANSLATION_FILE_NAMES["edx_platform"]
        / TRANSLATION_FILE_NAMES["conf_dir"]
        / TRANSLATION_FILE_NAMES["locale_dir"]
        / backend_locale
        / TRANSLATION_FILE_NAMES["lc_messages"]
    )

    for po_file_name in BACKEND_PO_FILES:
        en_file = (
            base_dir
            / TRANSLATION_FILE_NAMES["edx_platform"]
            / TRANSLATION_FILE_NAMES["conf_dir"]
            / TRANSLATION_FILE_NAMES["locale_dir"]
            / "en"
            / TRANSLATION_FILE_NAMES["lc_messages"]
            / po_file_name
        )
        target_file = locale_dir / po_file_name

        if not en_file.exists():
            continue

        try:
            stats = sync_or_create_po_file(
                en_file, target_file, backend_locale, iso_code
            )
            backend_stats["added"] += stats.get("added", 0)
        except (OSError, polib.POFileError, ValueError):
            continue

    return backend_stats


def sync_all_translations(
    base_dir: Path,
    lang_code: str,
    iso_code: str | None = None,
    *,
    skip_backend: bool = False,
) -> dict:
    """
    Sync all translation files for a language.
    Returns summary stats.
    """
    if iso_code is None:
        iso_code = lang_code

    frontend_stats = _sync_frontend_translations(base_dir, iso_code)
    backend_stats = (
        _sync_backend_translations(base_dir, lang_code, iso_code)
        if not skip_backend
        else {"added": 0}
    )

    return {
        "frontend": frontend_stats,
        "backend": backend_stats,
    }
