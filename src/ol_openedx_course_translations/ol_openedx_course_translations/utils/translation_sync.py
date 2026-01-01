"""Translation synchronization module for syncing and managing translation files."""

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

import polib

from ol_openedx_course_translations.utils.constants import (
    BACKEND_PO_FILES,
    DEFAULT_JSON_INDENT,
    DEFAULT_PLURAL_FORM,
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


def load_json_file(file_path: Path) -> dict:
    """Load a JSON translation file."""
    if not file_path.exists():
        return {}
    try:
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Error parsing JSON file {file_path}: {e}")


def save_json_file(file_path: Path, data: dict, indent: int = DEFAULT_JSON_INDENT):
    """Save a JSON translation file with proper formatting."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
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
    Returns dict with stats: {'action': 'created'|'synced'|'skipped', 'added': int, 'fixed': int, 'removed': int}
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
                stats["fixed"] += 1

            if typo_key in ordered_data:
                del ordered_data[typo_key]
                stats["removed"] += 1

        for key in en_data:
            if key not in ordered_data:
                ordered_data[key] = ""
                stats["added"] += 1

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

    header = f"""msgid ""
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
    return header


def parse_po_file(po_file: Path) -> dict[str, str]:
    """
    Parse a PO file and extract msgid -> msgstr mappings.
    For plural forms, uses msgid as the key (msgid_plural entries are handled separately).
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
    Returns dict with structure: {msgid: {'msgstr': str, 'msgid_plural': str, 'msgstr_plural': dict,
                                         'locations': List[str], 'flags': List[str], 'is_plural': bool}}
    Uses polib if available, falls back to manual parsing.
    """
    if not po_file.exists():
        return {}

    po = polib.pofile(str(po_file))
    entries = {}
    for entry in po:
        if entry.msgid:  # Skip empty header msgid
            # Convert occurrences from (filepath, line) tuples to strings like "filepath:line"
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

        # Create a set of existing entries (msgid + msgid_plural for plural entries)
        existing_entries = set()
        for entry in target_po:
            if entry.msgid:
                if entry.msgid_plural:
                    existing_entries.add((entry.msgid, entry.msgid_plural))
                else:
                    existing_entries.add((entry.msgid, None))

        # Add missing entries from English file
        added_count = 0
        for entry in en_po:
            if not entry.msgid:  # Skip header
                continue

            # Check if entry exists
            entry_key = (
                entry.msgid,
                entry.msgid_plural if entry.msgid_plural else None,
            )
            if entry_key not in existing_entries:
                # Create new entry with empty translation
                new_entry = polib.POEntry(
                    msgid=entry.msgid,
                    msgid_plural=entry.msgid_plural,
                    occurrences=entry.occurrences,
                    flags=entry.flags,
                )
                if entry.msgid_plural:
                    # Initialize plural forms (at least 2)
                    # Use the number of forms from English entry or default to 2
                    num_forms = max(
                        2, len(entry.msgstr_plural) if entry.msgstr_plural else 2
                    )
                    new_entry.msgstr_plural = dict.fromkeys(range(num_forms), "")
                else:
                    new_entry.msgstr = ""
                target_po.append(new_entry)
                added_count += 1

        if added_count > 0:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_po.save(str(target_file))

        stats["added"] = added_count
    else:
        # File doesn't exist: create new with all entries from English
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

            new_entry = polib.POEntry(
                msgid=entry.msgid,
                msgid_plural=entry.msgid_plural,
                occurrences=entry.occurrences,
                flags=entry.flags,
            )
            if entry.msgid_plural:
                # Initialize plural forms
                num_forms = max(
                    2, len(entry.msgstr_plural) if entry.msgstr_plural else 2
                )
                new_entry.msgstr_plural = dict.fromkeys(range(num_forms), "")
            else:
                new_entry.msgstr = ""
            target_po.append(new_entry)
            added_count += 1

        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_po.save(str(target_file))
        stats["added"] = added_count

    return stats


def extract_empty_keys(
    base_dir: Path,
    lang_code: str,
    iso_code: str | None = None,
    skip_backend: bool = False,
) -> list[dict]:
    """
    Extract all empty translation keys for a language.
    Returns list of dicts with: {'app': str, 'key': str, 'english': str, 'file_type': 'json'|'po'}
    """
    if iso_code is None:
        iso_code = lang_code

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
            continue

        try:
            target_data = load_json_file(target_file)
            en_data = load_json_file(en_file)

            # Use set for faster lookup if target_data is large
            for key in en_data:
                target_value = target_data.get(key, "")
                if not target_value or (
                    isinstance(target_value, str) and not target_value.strip()
                ):
                    empty_keys.append(
                        {
                            "app": app,
                            "key": key,
                            "english": en_data[key],
                            "translation": "",
                            "file_type": "json",
                            "file_path": str(target_file.resolve()),
                        }
                    )
        except (OSError, ValueError, json.JSONDecodeError):
            # More specific exception handling
            continue

    if not skip_backend:
        # Use iso_code for backend locale directory if provided, otherwise use lang_code
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
                # Parse both files once and reuse
                target_po = polib.pofile(str(target_file))
                en_po = polib.pofile(str(en_file))

                # Create dict of target entries: msgid -> entry for O(1) lookup
                target_entries_dict = {
                    entry.msgid: entry for entry in target_po if entry.msgid
                }

                for entry in en_po:
                    if not entry.msgid:  # Skip header
                        continue

                    # Check if entry is missing or empty in target
                    target_entry = target_entries_dict.get(entry.msgid)
                    if target_entry is None:
                        # Entry doesn't exist
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
                    elif entry.msgid_plural:
                        # Plural entry - check if plural forms are empty
                        plural_empty = any(
                            not target_entry.msgstr_plural.get(i, "").strip()
                            for i in range(len(target_entry.msgstr_plural))
                        )
                        if plural_empty:
                            empty_keys.append(
                                {
                                    "app": "edx-platform",
                                    "key": entry.msgid,
                                    "english": entry.msgid,
                                    "translation": "",
                                    "file_type": "po",
                                    "file_path": str(target_file.resolve()),
                                    "po_file": po_file_name,
                                    "is_plural": True,
                                    "msgid_plural": entry.msgid_plural,
                                }
                            )
                    elif not target_entry.msgstr or not target_entry.msgstr.strip():
                        # Singular entry - check if empty
                        empty_keys.append(
                            {
                                "app": "edx-platform",
                                "key": entry.msgid,
                                "english": entry.msgid,
                                "translation": "",
                                "file_type": "po",
                                "file_path": str(target_file.resolve()),
                                "po_file": po_file_name,
                                "is_plural": False,
                                "msgid_plural": None,
                            }
                        )
            except (OSError, polib.POFileError, ValueError):
                # More specific exception handling
                continue

    return empty_keys


def apply_json_translations(file_path: Path, translations: dict[str, str]) -> int:
    """
    Apply translations to a JSON file.
    Returns number of translations applied.
    """
    data = load_json_file(file_path)
    applied = 0

    for key, translation in translations.items():
        if key in data:
            # Check if the value is empty (empty string, whitespace only, or None)
            current_value = data[key]
            if not current_value or (
                isinstance(current_value, str) and not current_value.strip()
            ):
                data[key] = translation
                applied += 1

    if applied > 0:
        save_json_file(file_path, data)

    return applied


def load_glossary(glossary_path: Path, lang_code: str = "") -> dict[str, Any]:
    """
    Load glossary for a language from a text file.
    Parses text format with term mappings like: - 'english term' -> 'translation'
    Returns dict mapping English -> Translation (string or dict for plural forms).

    Args:
        glossary_path: Path to the glossary text file.
        lang_code: Language code (currently unused, kept for API compatibility).

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
        with open(glossary_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                # Skip empty lines, comments, and headers
                if not line or line.startswith("#"):
                    continue

                # Parse lines like: - 'english term' -> 'translation'
                if line.startswith("- ") and "->" in line:
                    # Extract the mapping
                    # Format: - 'english term' -> 'translation'
                    line = line[2:].strip()  # Remove leading '- '
                    parts = line.split("->", 1)

                    if len(parts) == 2:
                        english_term = parts[0].strip().strip("'\"")
                        translation = parts[1].strip().strip("'\"")

                        if english_term and translation:
                            glossary[english_term] = translation

        return glossary

    except (OSError, UnicodeDecodeError):
        # Log specific file-related errors but return empty dict to allow continuation
        # In a library function, we can't use stdout, so we just return empty dict
        # The caller can handle logging if needed
        return {}
    except Exception:
        # Catch-all for any other unexpected errors
        return {}


def match_glossary_term(
    text: str, glossary: dict[str, Any] | None, exact_match: bool = True
) -> Any | None:
    """
    Match text against glossary terms.
    Returns translation (string or dict with 'singular'/'plural') if match found, None otherwise.
    Supports both simple format ("term": "translation") and plural format ("term": {"singular": "...", "plural": "..."}).

    Args:
        text: The text to match against glossary terms.
        glossary: Dictionary mapping English terms to translations, or None.
        exact_match: If True, only exact matches are returned. If False, case-insensitive and partial matches are allowed.

    Returns:
        Translation string/dict if match found, None otherwise.
    """
    if not glossary:
        return None

    if text in glossary:
        value = glossary[text]
        # Return as-is: string for singular, dict for plural
        return value

    if not exact_match:
        text_lower = text.lower().strip()
        for term, translation in glossary.items():
            if term.lower().strip() == text_lower:
                return translation

        for term, translation in glossary.items():
            if term.lower() in text_lower or text_lower in term.lower():
                return translation

    return None


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

    for entry in po:
        if not entry.msgid:
            continue

        if entry.msgid in translations:
            translation = translations[entry.msgid]

            if entry.msgid_plural:
                # Plural entry
                if (
                    isinstance(translation, dict)
                    and "singular" in translation
                    and "plural" in translation
                ):
                    # Both singular and plural provided
                    plural_applied = False
                    if not entry.msgstr_plural.get(0, "").strip():
                        entry.msgstr_plural[0] = translation["singular"]
                        plural_applied = True
                    if (
                        len(entry.msgstr_plural) > 1
                        and not entry.msgstr_plural.get(1, "").strip()
                    ):
                        entry.msgstr_plural[1] = translation["plural"]
                        plural_applied = True
                    if plural_applied:
                        applied += 1
                elif isinstance(translation, str) and translation:
                    # Single translation - apply to all empty plural forms
                    plural_applied = False
                    for i in range(len(entry.msgstr_plural)):
                        if not entry.msgstr_plural.get(i, "").strip():
                            entry.msgstr_plural[i] = translation
                            plural_applied = True
                    if plural_applied:
                        applied += 1
            # Singular entry - translation should be a string
            elif (
                isinstance(translation, str)
                and translation
                and (not entry.msgstr or not entry.msgstr.strip())
            ):
                entry.msgstr = translation
                applied += 1

    if applied > 0:
        po.save(str(file_path))

    return applied


def sync_all_translations(
    base_dir: Path,
    lang_code: str,
    iso_code: str | None = None,
    skip_backend: bool = False,
) -> dict:
    """
    Sync all translation files for a language.
    Returns summary stats.
    """
    if iso_code is None:
        iso_code = lang_code

    frontend_stats = {"added": 0, "fixed": 0, "removed": 0, "created": 0, "synced": 0}
    backend_stats = {"added": 0}

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
        except (OSError, ValueError, json.JSONDecodeError):
            # More specific exception handling
            continue

    if not skip_backend:
        # Use iso_code for backend locale directory if provided, otherwise use lang_code
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
                # More specific exception handling
                continue

    return {
        "frontend": frontend_stats,
        "backend": backend_stats,
    }
