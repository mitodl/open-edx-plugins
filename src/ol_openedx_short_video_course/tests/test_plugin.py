"""
Tests for ol_openedx_short_video_course.
"""

# ruff: noqa: PLC0415, PLR2004, S108, PLR0913, ARG002

import csv
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest
from ol_openedx_short_video_course.utils.csv_parser import (
    CsvRow,
    group_rows,
    parse_csv,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CSV_HEADER = [
    "course_name",
    "course_key",
    "section_name",
    "subsection_name",
    "vertical_name",
    "edx_video_id",
]

COURSE_KEY = "course-v1:ORG+NUM+RUN"
COURSE_KEY_2 = "course-v1:ORG+NUM2+RUN"
COURSE_NAME = "Test Short Video Course"
VID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _make_csv(tmp_path: Path, rows: list[list[str]]) -> Path:
    """Write a CSV file with the standard header and given data rows."""
    p = tmp_path / "mapping.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_HEADER)
        writer.writerows(rows)
    return p


def _make_row(
    course_name: str = COURSE_NAME,
    course_key: str = COURSE_KEY,
    section_name: str = "Section 1",
    subsection_name: str = "Subsection 1",
    vertical_name: str = "Unit 1",
    edx_video_id: str = VID,
) -> list[str]:
    return [
        course_name,
        course_key,
        section_name,
        subsection_name,
        vertical_name,
        edx_video_id,
    ]


class _FakeLocation:
    def __init__(self, block_id: str):
        self.block_id = block_id

    def __str__(self) -> str:
        return self.block_id


class _FakeBlock:
    def __init__(self, block_id: str, display_name: str = ""):
        self.location = _FakeLocation(block_id)
        self.display_name = display_name


class _NullContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _patch_modulestore(fake_store):
    """Patch xmodule.modulestore.django.modulestore to return fake_store."""
    django_mod = types.ModuleType("xmodule.modulestore.django")
    django_mod.modulestore = lambda: fake_store

    modulestore_pkg = types.ModuleType("xmodule.modulestore")
    modulestore_pkg.django = django_mod

    xmodule_pkg = types.ModuleType("xmodule")
    xmodule_pkg.modulestore = modulestore_pkg

    return patch.dict(
        sys.modules,
        {
            "xmodule": xmodule_pkg,
            "xmodule.modulestore": modulestore_pkg,
            "xmodule.modulestore.django": django_mod,
        },
    )


# ---------------------------------------------------------------------------
# csv_parser — parse_csv
# ---------------------------------------------------------------------------


class TestParseCsv:
    def test_happy_path(self, tmp_path):
        """Parses a valid row into a CsvRow."""
        p = _make_csv(tmp_path, [_make_row()])
        rows = parse_csv(str(p))
        assert len(rows) == 1
        row = rows[0]
        assert row.course_key_str == COURSE_KEY
        assert row.course_name == COURSE_NAME
        assert row.section_name == "Section 1"
        assert row.subsection_name == "Subsection 1"
        assert row.vertical_name == "Unit 1"
        assert row.edx_video_id == VID

    def test_empty_video_id_allowed(self, tmp_path):
        """Accepts rows where edx_video_id is empty."""
        p = _make_csv(tmp_path, [_make_row(edx_video_id="")])
        rows = parse_csv(str(p))
        assert len(rows) == 1
        assert rows[0].edx_video_id == ""

    def test_file_not_found(self):
        """Raises FileNotFoundError when the CSV path does not exist."""
        with pytest.raises(FileNotFoundError):
            parse_csv("/nonexistent/path/mapping.csv")

    def test_missing_column_raises(self, tmp_path):
        """Raises ValueError when required CSV columns are missing."""
        p = tmp_path / "bad.csv"
        p.write_text("course_name,course_key\nFoo,course-v1:X+Y+Z\n")
        with pytest.raises(ValueError, match="missing required columns"):
            parse_csv(str(p))

    def test_empty_required_field_raises(self, tmp_path):
        """Raises ValueError when a required non-video field is blank."""
        p = _make_csv(
            tmp_path,
            [_make_row(section_name="")],  # section_name is blank
        )
        with pytest.raises(ValueError, match="'section_name' must not be empty"):
            parse_csv(str(p))

    def test_empty_csv_raises(self, tmp_path):
        """Raises ValueError when the CSV has a header but no data rows."""
        p = tmp_path / "empty.csv"
        p.write_text(",".join(CSV_HEADER) + "\n")
        with pytest.raises(ValueError, match="no data rows"):
            parse_csv(str(p))

    def test_multiple_rows_parsed(self, tmp_path):
        """Parses multiple rows correctly."""
        p = _make_csv(
            tmp_path,
            [
                _make_row(section_name="Sec 1", subsection_name="Sub 1"),
                _make_row(section_name="Sec 1", subsection_name="Sub 2"),
                _make_row(
                    course_key=COURSE_KEY_2,
                    section_name="Sec A",
                    subsection_name="Sub A",
                ),
            ],
        )
        rows = parse_csv(str(p))
        assert len(rows) == 3
        assert rows[0].section_name == "Sec 1"
        assert rows[1].subsection_name == "Sub 2"
        assert rows[2].course_key_str == COURSE_KEY_2


# ---------------------------------------------------------------------------
# csv_parser — group_rows
# ---------------------------------------------------------------------------


class TestGroupRows:
    def test_groups_by_course_key(self, tmp_path):
        """Groups rows by course_key, preserving insertion order."""
        rows = [
            CsvRow(COURSE_NAME, COURSE_KEY, "S1", "Sub1", "U1", VID, 2),
            CsvRow(COURSE_NAME, COURSE_KEY, "S1", "Sub2", "U2", VID, 3),
            CsvRow("Other Course", COURSE_KEY_2, "S1", "Sub1", "U1", "", 4),
        ]
        groups = group_rows(rows)
        assert list(groups.keys()) == [COURSE_KEY, COURSE_KEY_2]
        assert len(groups[COURSE_KEY]) == 2
        assert len(groups[COURSE_KEY_2]) == 1

    def test_preserves_row_order_within_group(self):
        """Rows within a group retain their original CSV order."""
        rows = [
            CsvRow(COURSE_NAME, COURSE_KEY, "Sec A", "Sub 1", "U1", VID, 2),
            CsvRow(COURSE_NAME, COURSE_KEY, "Sec B", "Sub 1", "U2", VID, 3),
            CsvRow(COURSE_NAME, COURSE_KEY, "Sec A", "Sub 2", "U3", "", 4),
        ]
        groups = group_rows(rows)
        section_names = [r.section_name for r in groups[COURSE_KEY]]
        assert section_names == ["Sec A", "Sec B", "Sec A"]


# ---------------------------------------------------------------------------
# course_creator — build_course_structure
# ---------------------------------------------------------------------------


class TestBuildCourseStructure:
    def test_creates_section_subsection_unit_video(self):
        """Creates the full hierarchy for a simple single-section course."""
        from ol_openedx_short_video_course.utils.course_creator import (
            build_course_structure,
        )
        from opaque_keys.edx.keys import CourseKey

        rows = [
            CsvRow(COURSE_NAME, COURSE_KEY, "Intro", "Overview", "Welcome", VID, 2),
        ]

        class FakeStore:
            def __init__(self):
                self.created: list[tuple] = []

            def get_course(self, _key, depth=None):
                return _FakeBlock("course", "Test Course")

            def bulk_operations(self, _key):
                return _NullContext()

            def create_child(self, _user_id, parent_loc, block_type, block_id, fields):
                self.created.append((block_type, block_id, fields, str(parent_loc)))
                return _FakeBlock(block_id, fields.get("display_name", ""))

        fake_store = FakeStore()
        with _patch_modulestore(fake_store):
            stats = build_course_structure(
                CourseKey.from_string(COURSE_KEY), rows, user_id=1
            )

        block_types = [c[0] for c in fake_store.created]
        assert "chapter" in block_types
        assert "sequential" in block_types
        assert "vertical" in block_types
        assert "video" in block_types
        assert stats.sections == 1
        assert stats.subsections == 1
        assert stats.units == 1

    def test_multiple_sections_and_subsections(self):
        """Creates multiple sections, each with their own subsections."""
        from ol_openedx_short_video_course.utils.course_creator import (
            build_course_structure,
        )
        from opaque_keys.edx.keys import CourseKey

        rows = [
            CsvRow(COURSE_NAME, COURSE_KEY, "Sec A", "Sub 1", "Unit 1", VID, 2),
            CsvRow(COURSE_NAME, COURSE_KEY, "Sec A", "Sub 2", "Unit 2", VID, 3),
            CsvRow(COURSE_NAME, COURSE_KEY, "Sec B", "Sub 1", "Unit 3", "", 4),
        ]

        class FakeStore:
            def __init__(self):
                self.created: list[tuple] = []

            def get_course(self, _key, depth=None):
                return _FakeBlock("course")

            def bulk_operations(self, _key):
                return _NullContext()

            def create_child(self, _user_id, parent_loc, block_type, block_id, fields):
                self.created.append((block_type, block_id, fields, str(parent_loc)))
                return _FakeBlock(block_id, fields.get("display_name", ""))

        fake_store = FakeStore()
        with _patch_modulestore(fake_store):
            stats = build_course_structure(
                CourseKey.from_string(COURSE_KEY), rows, user_id=1
            )

        chapters = [c for c in fake_store.created if c[0] == "chapter"]
        sequentials = [c for c in fake_store.created if c[0] == "sequential"]
        verticals = [c for c in fake_store.created if c[0] == "vertical"]
        assert len(chapters) == 2
        assert len(sequentials) == 3
        assert len(verticals) == 3
        assert stats.sections == 2
        assert stats.subsections == 3
        assert stats.units == 3

    def test_video_block_without_edx_video_id(self):
        """Creates a video block even when edx_video_id is empty."""
        from ol_openedx_short_video_course.utils.course_creator import (
            build_course_structure,
        )
        from opaque_keys.edx.keys import CourseKey

        rows = [
            CsvRow(COURSE_NAME, COURSE_KEY, "Sec", "Sub", "Unit", "", 2),
        ]

        class FakeStore:
            def __init__(self):
                self.video_fields: dict = {}

            def get_course(self, _key, depth=None):
                return _FakeBlock("course")

            def bulk_operations(self, _key):
                return _NullContext()

            def create_child(self, _user_id, parent_loc, block_type, block_id, fields):
                if block_type == "video":
                    self.video_fields = fields
                return _FakeBlock(block_id)

        fake_store = FakeStore()
        with _patch_modulestore(fake_store):
            build_course_structure(CourseKey.from_string(COURSE_KEY), rows, user_id=1)

        assert "edx_video_id" not in fake_store.video_fields

    def test_video_block_with_edx_video_id(self):
        """Sets edx_video_id on the video block when provided."""
        from ol_openedx_short_video_course.utils.course_creator import (
            build_course_structure,
        )
        from opaque_keys.edx.keys import CourseKey

        rows = [
            CsvRow(COURSE_NAME, COURSE_KEY, "Sec", "Sub", "Unit", VID, 2),
        ]

        class FakeStore:
            def __init__(self):
                self.video_fields: dict = {}

            def get_course(self, _key, depth=None):
                return _FakeBlock("course")

            def bulk_operations(self, _key):
                return _NullContext()

            def create_child(self, _user_id, parent_loc, block_type, block_id, fields):
                if block_type == "video":
                    self.video_fields = fields
                return _FakeBlock(block_id)

        fake_store = FakeStore()
        with _patch_modulestore(fake_store):
            build_course_structure(CourseKey.from_string(COURSE_KEY), rows, user_id=1)

        assert fake_store.video_fields.get("edx_video_id") == VID


# ---------------------------------------------------------------------------
# services — generate_custom_courses
# ---------------------------------------------------------------------------


class TestServices:
    def test_dry_run_returns_plan_without_writes(self):
        """Returns planned structure in dry-run mode without creating courses."""
        from ol_openedx_short_video_course import services

        rows = [
            CsvRow(COURSE_NAME, COURSE_KEY, "Sec 1", "Sub 1", "Unit 1", VID, 2),
        ]
        groups = {COURSE_KEY: rows}

        with (
            patch.object(services, "parse_csv", return_value=rows),
            patch.object(services, "group_rows", return_value=groups),
            patch.object(services, "create_course") as mock_create,
            patch.object(services, "build_course_structure") as mock_build,
        ):
            result = services.generate_custom_courses(
                csv_path="/tmp/mapping.csv",
                user_id=1,
                dry_run=True,
            )

        assert result.success is True
        assert result.dry_run is True
        assert COURSE_KEY in result.planned_ops
        assert result.planned_ops[COURSE_KEY]["course_name"] == COURSE_NAME
        assert result.planned_ops[COURSE_KEY]["total_units"] == 1
        mock_create.assert_not_called()
        mock_build.assert_not_called()

    def test_invalid_course_key_fails_validation(self):
        """Returns validation error when a course key is malformed."""
        from ol_openedx_short_video_course import services

        rows = [
            CsvRow(COURSE_NAME, "not-a-valid-key", "Sec", "Sub", "Unit", VID, 2),
        ]

        with patch.object(services, "parse_csv", return_value=rows):
            result = services.generate_custom_courses(
                csv_path="/tmp/mapping.csv",
                user_id=1,
            )

        assert result.success is False
        assert any("invalid course key" in e for e in result.validation_errors)

    def test_live_run_creates_each_course(self):
        """Calls create_course and build_course_structure for each course key."""
        from ol_openedx_short_video_course.utils.course_creator import CreationStats

        from ol_openedx_short_video_course import services

        rows = [
            CsvRow(COURSE_NAME, COURSE_KEY, "Sec", "Sub", "Unit", VID, 2),
            CsvRow("Course 2", COURSE_KEY_2, "Sec", "Sub", "Unit", "", 3),
        ]
        groups = {COURSE_KEY: [rows[0]], COURSE_KEY_2: [rows[1]]}

        with (
            patch.object(services, "parse_csv", return_value=rows),
            patch.object(services, "group_rows", return_value=groups),
            patch.object(services, "create_course") as mock_create,
            patch.object(
                services,
                "build_course_structure",
                return_value=CreationStats(sections=1, subsections=1, units=1),
            ) as mock_build,
        ):
            result = services.generate_custom_courses(
                csv_path="/tmp/mapping.csv",
                user_id=1,
                dry_run=False,
            )

        assert result.success is True
        assert len(result.run_results) == 2
        assert mock_create.call_count == 2
        assert mock_build.call_count == 2

    def test_course_creation_error_is_captured(self):
        """Records a failed run when course creation raises an error."""
        from ol_openedx_short_video_course import services

        rows = [CsvRow(COURSE_NAME, COURSE_KEY, "Sec", "Sub", "Unit", VID, 2)]
        groups = {COURSE_KEY: rows}

        with (
            patch.object(services, "parse_csv", return_value=rows),
            patch.object(services, "group_rows", return_value=groups),
            patch.object(
                services, "create_course", side_effect=ValueError("already exists")
            ),
        ):
            result = services.generate_custom_courses(
                csv_path="/tmp/mapping.csv",
                user_id=1,
            )

        assert result.success is False
        assert result.run_results[0].success is False
        assert "already exists" in result.run_results[0].error

    def test_parse_error_returns_validation_failure(self):
        """Returns validation failure when CSV parsing raises."""
        from ol_openedx_short_video_course import services

        with patch.object(
            services, "parse_csv", side_effect=ValueError("missing required columns")
        ):
            result = services.generate_custom_courses(
                csv_path="/tmp/bad.csv",
                user_id=1,
            )

        assert result.success is False
        assert any("missing required columns" in e for e in result.validation_errors)
