"""Constants for ol-openedx-uai-content-customization plugin."""

# Industry short codes used in course key generation.
# "Original industry" has no code — only a length code is appended.
INDUSTRY_CODES = {
    "Healthcare": "HC",
    "Finance": "F",
    "Energy": "E",
    "Original industry": "",
}

# Duration label → short code used in course key generation.
# Numeric minutes (e.g. "10") are treated as Short; "long" as Full.
DURATION_CODE_SHORT = "S"
DURATION_CODE_FULL = "F"

DURATION_CODES = {
    "short": DURATION_CODE_SHORT,
    "long": DURATION_CODE_FULL,
}

# Duration threshold: any numeric value at or below this (in minutes) maps to
# "Short" (code "S"). Values above it map to "Full" (code "F").
# The spec defines short as ≤10 min; 30 allows headroom for slightly longer
# short-form variants without requiring a CSV format change.
SHORT_DURATION_THRESHOLD = 30

# Display name for the top-level section added to every generated course
LECTURES_SECTION_DISPLAY_NAME = "Lectures"

# CSV column names — customized video metadata CSV
CSV_COL_COURSE_KEY = "Course Key"
CSV_COL_INDUSTRY = "Industry"
CSV_COL_DURATION = "duration_minutes"
CSV_COL_VIDEO_FILE = "Video File Name"
CSV_COL_VIDEO_TITLE = "Video Title (Lecture Title)"
CSV_COL_MODULE_NAME = "Module Name"

# CSV column names — Open edX video asset CSV
CSV_COL_ASSET_NAME = "Name"
CSV_COL_ASSET_VIDEO_ID = "Video ID"

# Required columns for each CSV — used to give early, clear error messages
REQUIRED_CUSTOMIZED_CSV_COLS = [
    CSV_COL_COURSE_KEY,
    CSV_COL_INDUSTRY,
    CSV_COL_DURATION,
    CSV_COL_VIDEO_FILE,
    CSV_COL_VIDEO_TITLE,
    CSV_COL_MODULE_NAME,
]

REQUIRED_ASSET_CSV_COLS = [
    CSV_COL_ASSET_NAME,
    CSV_COL_ASSET_VIDEO_ID,
]
