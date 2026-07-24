"""CSV parsing and video-mapping utilities for ol-openedx-uai-content-customization."""

import csv
import io
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import requests
from django.utils.html import escape
from opaque_keys.edx.keys import CourseKey

from ol_openedx_uai_content_customization.constants import (
    CSV_COL_COURSE_INTRO,
    CSV_COL_COURSE_KEY,
    CSV_COL_DURATION,
    CSV_COL_INDUSTRY,
    DURATION_CODES,
    INDUSTRY_CODES,
)

GOOGLE_SHEETS_HOST = "docs.google.com"
GOOGLE_SHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")
GOOGLE_SHEET_GID_RE = re.compile(r"[#&?]gid=([0-9]+)")
GOOGLE_SHEET_REQUEST_TIMEOUT = 30


def is_url(source):
    """Return True if *source* is an http(s) URL rather than a local path."""
    return urlparse(str(source)).scheme in ("http", "https")


def is_google_sheets_url(source):
    """Return True if *source* is a docs.google.com Sheets link."""
    parsed = urlparse(str(source))
    return (
        parsed.netloc.lower() == GOOGLE_SHEETS_HOST and "/spreadsheets/" in parsed.path
    )


def build_google_sheet_csv_export_url(sheet_url):
    """
    Convert a public Google Sheets link into a CSV export link.

    Accepts standard share/edit links copied from the browser, e.g.::

        https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit#gid=<GID>
        https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit?usp=sharing

    Links that already point at a CSV export or "Publish to web" endpoint
    (containing ``/export`` or ``output=csv``) are returned unchanged.

    Args:
        sheet_url: A ``docs.google.com`` Sheets URL, as copied from the
            share dialog.

    Returns:
        A URL that returns CSV content when fetched.

    Raises:
        ValueError: if no spreadsheet ID can be found in the URL.
    """
    if "/export" in sheet_url or "output=csv" in sheet_url:
        return sheet_url

    match = GOOGLE_SHEET_ID_RE.search(sheet_url)
    if not match:
        msg = f"Could not find a spreadsheet ID in Google Sheets URL: {sheet_url!r}"
        raise ValueError(msg)
    sheet_id = match.group(1)

    gid_match = GOOGLE_SHEET_GID_RE.search(sheet_url)
    gid = gid_match.group(1) if gid_match else "0"

    return (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    )


def fetch_csv_text(source):
    """
    Download CSV content from a URL.

    ``docs.google.com`` Sheets share/edit links are converted to their CSV
    export link first. Any other URL is treated as already pointing at CSV
    content (e.g. a direct CSV/export link) and is fetched as-is.

    Args:
        source: A Google Sheets share/edit URL, or a direct CSV/export URL.

    Returns:
        str: The raw CSV content fetched from the URL.

    Raises:
        requests.RequestException: on network failure or a non-2xx response.
    """
    fetch_url = (
        build_google_sheet_csv_export_url(source)
        if is_google_sheets_url(source)
        else source
    )
    response = requests.get(fetch_url, timeout=GOOGLE_SHEET_REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.text


def parse_csv(source):
    """
    Read CSV data from a local file path or a public Google Sheets URL.

    Args:
        source: A filesystem path to a CSV file, or an http(s) URL — either
            a ``docs.google.com`` Sheets share/edit link or a direct
            CSV/export link.

    Returns:
        tuple: A 2-tuple ``(rows, fieldnames)`` where *rows* is a list of
        ``dict`` objects (one per data row) and *fieldnames* is the list of
        column header strings as they appear in the source.  Both are empty
        lists when there is no header row at all.
    """
    if is_url(source):
        reader = csv.DictReader(io.StringIO(fetch_csv_text(source)))
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    else:
        with Path(source).open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)

    fieldnames = [col.lower() for col in fieldnames]
    rows = [{col.lower(): value for col, value in row.items()} for row in rows]
    return rows, fieldnames


def validate_csv_columns(fieldnames, required_cols, csv_label):
    """
    Raise ValueError if any required column is absent from the CSV headers.

    Args:
        fieldnames: List of column header strings returned by parse_csv().
        required_cols: Iterable of column names that must be present.
        csv_label: Human-readable label used in the error message.

    Raises:
        ValueError: describing which columns are missing.
    """
    actual_cols = {col.lower() for col in fieldnames}
    missing = [col for col in required_cols if col.lower() not in actual_cols]
    if missing:
        msg = f"{csv_label} is missing required columns: {', '.join(missing)}"
        raise ValueError(msg)


def resolve_duration_code(duration_value):
    """
    Convert a duration cell value into a Short/Full code.

    The CSV must provide explicit values: "short" or "long"
    (case-insensitive).

    Args:
        duration_value: Raw string from the Duration column.

    Returns:
        "S" or "F"

    Raises:
        ValueError: if the value is not one of "short" or "long".
    """
    value = str(duration_value).strip().lower()

    if value in DURATION_CODES:
        return DURATION_CODES[value]

    msg = (
        "Unrecognised duration value "
        f"{duration_value!r}. Expected one of: {', '.join(DURATION_CODES)}"
    )
    raise ValueError(msg)


def build_new_course_key(original_key, industry, duration_value):
    """
    Generate a new course key for the given industry and duration.

    Format:  course-v1:ORG+NUMBER.<DURATION>[.<INDUSTRY>]+RUN

    For "Original" industry no industry code is appended, so the format is:
        course-v1:ORG+NUMBER.<DURATION>+RUN

    Args:
        original_key: e.g. "course-v1:UAI_SOURCE+UAI.2+1T2026"
        industry: Industry name string as it appears in the CSV.
        duration_value: Raw Duration column value.

    Returns:
        New course key string.
    """
    parsed = CourseKey.from_string(original_key)
    org = parsed.org
    number = parsed.course
    run = parsed.run

    dur_code = resolve_duration_code(duration_value)

    if industry not in INDUSTRY_CODES:
        known = ", ".join(INDUSTRY_CODES)
        msg = f"Unrecognised industry {industry!r}. Must be one of: {known}"
        raise ValueError(msg)
    ind_code = INDUSTRY_CODES[industry]

    if ind_code:
        new_number = f"{number}.{dur_code}.{ind_code}"
    else:
        new_number = f"{number}.{dur_code}"

    return f"course-v1:{org}+{new_number}+{run}"


def group_videos_by_course(customized_rows):
    """
    Group video rows by (original_course_key, industry, duration).

    Returns:
        dict mapping (course_key, industry, duration) → list of row dicts.
    """
    groups = defaultdict(list)
    for row in customized_rows:
        key = (
            row[CSV_COL_COURSE_KEY],
            row[CSV_COL_INDUSTRY],
            row[CSV_COL_DURATION],
        )
        groups[key].append(row)
    return groups


def build_course_intro_lookup(customized_rows):
    """
    Build lookup maps for resolving a course intro by specificity.

    Uses first-row-wins behavior when multiple rows provide conflicting
    ``course_intro`` values for the same lookup key.

    Returns:
        dict with keys:
            - "exact": (course_key, industry, duration) -> intro
            - "industry": (course_key, industry) -> intro
            - "original": course_key -> intro (from Original industry rows)
    """
    exact = {}
    industry = {}
    original = {}

    for row in customized_rows:
        intro_text = normalize_course_intro(row.get(CSV_COL_COURSE_INTRO, ""))
        if not intro_text:
            continue

        course_key = row[CSV_COL_COURSE_KEY]
        industry_name = row[CSV_COL_INDUSTRY]
        duration = row[CSV_COL_DURATION]

        exact.setdefault((course_key, industry_name, duration), intro_text)
        industry.setdefault((course_key, industry_name), intro_text)

        # Short code for "Original" industry is empty string.
        # We use this to identify which rows are intended
        # to provide original-industry fallback intros.
        if INDUSTRY_CODES.get(industry_name) == "":
            original.setdefault(course_key, intro_text)

    return {
        "exact": exact,
        "industry": industry,
        "original": original,
    }


def normalize_course_intro(intro_value):
    """
    Normalize course intro content to HTML.

    If the intro already contains HTML tags, return it as-is. Otherwise,
    treat the value as plain text and wrap it in a paragraph tag.

    Args:
        intro_value: Raw course_intro cell value from CSV.

    Returns:
        HTML string or empty string.
    """
    HTML_TAG_RE = re.compile(r"</?[a-zA-Z][a-zA-Z0-9]*(\s+[^<>]*)?>")
    intro_text = ("" if not intro_value else str(intro_value)).strip()
    if not intro_text:
        return ""

    if HTML_TAG_RE.search(intro_text):
        return intro_text

    return f"<p>{escape(intro_text)}</p>"


def resolve_course_intro(course_intro_lookup, course_key, industry, duration):
    """
    Resolve intro text for a generated course variant.

    Precedence:
        1. exact match: (course_key, industry, duration)
        2. industry-level: (course_key, industry)
        3. original-industry fallback: (course_key)
        4. no match -> empty string
    """
    exact = course_intro_lookup["exact"]
    by_industry = course_intro_lookup["industry"]
    original = course_intro_lookup["original"]

    return (
        exact.get((course_key, industry, duration))
        or by_industry.get((course_key, industry))
        or original.get(course_key)
        or ""
    )
