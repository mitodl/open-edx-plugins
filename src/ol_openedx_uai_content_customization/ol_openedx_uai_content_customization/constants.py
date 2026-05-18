"""Constants for ol-openedx-uai-content-customization plugin."""

INDUSTRY_CODES = {
    "Healthcare": "HC",
    "Finance": "F",
    "Energy": "E",
    "Original industry": "",
}

DURATION_CODE_SHORT = "S"
DURATION_CODE_FULL = "F"

DURATION_CODES = {
    "short": DURATION_CODE_SHORT,
    "long": DURATION_CODE_FULL,
}

LECTURES_SECTION_DISPLAY_NAME = "Lectures"

BLOCK_TYPE_CHAPTER = "chapter"
BLOCK_TYPE_SEQUENTIAL = "sequential"
BLOCK_TYPE_VERTICAL = "vertical"
BLOCK_TYPE_VIDEO = "video"

CSV_COL_COURSE_KEY = "course_key"
CSV_COL_INDUSTRY = "industry"
CSV_COL_DURATION = "duration"
CSV_COL_VIDEO_FILE = "video_file_name"
CSV_COL_VIDEO_TITLE = "video_title"
CSV_COL_MODULE_NAME = "module_name"

CSV_COL_ASSET_NAME = "name"
CSV_COL_ASSET_VIDEO_ID = "video_id"

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
