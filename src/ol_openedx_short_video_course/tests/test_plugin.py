"""
Tests for ol_openedx_short_video_course.

Run inside a Tutor/Open edX container:
    ./run_edx_integration_tests.sh --plugin ol_openedx_short_video_course --skip-build
"""

# ruff: noqa: PLC0415,PLR2004,S108,N818,TRY003,EM101

import csv
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest
from ol_openedx_short_video_course.utils.csv_parser import (
    CsvRow,
    derive_dest_course_key,
    group_rows,
    parse_csv,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_csv(tmp_path: Path, rows: list[list[str]]) -> Path:
    """Write a CSV file with the standard header and given data rows."""
    header = [
        "source_course_key",
        "section",
        "subsection",
        "action",
        "unit display name",
        "industry code",
        "type",
        "video ID",
    ]
    p = tmp_path / "mapping.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    return p


def _usage_key(block_type: str, block_id: str) -> str:
    """Build a valid usage key string for tests."""
    return f"block-v1:ORG+NUM+RUN+type@{block_type}+block@{block_id}"


class _FakeLocation:
    def __init__(self, block_id: str):
        self.block_id = block_id

    def __str__(self) -> str:
        return self.block_id


class _FakeBlock:
    def __init__(
        self,
        block_id: str,
        children: list["_FakeBlock"] | None = None,
        display_name: str = "",
    ):
        self.location = _FakeLocation(block_id)
        self._children = children or []
        self.display_name = display_name

    def get_children(self) -> list["_FakeBlock"]:
        return self._children


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


SOURCE = "course-v1:ORG+NUM+RUN"
SEC = "block-v1:ORG+NUM+RUN+type@chapter+block@sec1"
SUB = "block-v1:ORG+NUM+RUN+type@sequential+block@sub1"
VID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


# ---------------------------------------------------------------------------
# csv_parser — parse_csv
# ---------------------------------------------------------------------------


class TestParseCsv:
    def test_happy_path(self, tmp_path):
        p = _make_csv(
            tmp_path,
            [[SOURCE, SEC, SUB, "update", "Intro Video", "HC", "S", VID]],
        )
        rows = parse_csv(str(p))
        assert len(rows) == 1
        row = rows[0]
        assert row.action == "update"
        assert row.video_id == VID
        assert row.industry_code == "HC"
        assert row.type_code == "S"

    def test_keep_and_remove_have_empty_video_id(self, tmp_path):
        p = _make_csv(
            tmp_path,
            [
                [SOURCE, SEC, SUB, "keep", "Section 1", "HC", "S", ""],
                [
                    SOURCE,
                    SEC,
                    "block-v1:ORG+NUM+RUN+type@sequential+block@sub2",
                    "remove",
                    "",
                    "HC",
                    "S",
                    "",
                ],
            ],
        )
        rows = parse_csv(str(p))
        assert len(rows) == 2

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_csv("/nonexistent/path/mapping.csv")

    def test_missing_column_raises(self, tmp_path):
        p = tmp_path / "bad.csv"
        p.write_text("source_course_key,section,action\nval1,val2,keep\n")
        with pytest.raises(ValueError, match="missing required columns"):
            parse_csv(str(p))

    def test_invalid_action_raises(self, tmp_path):
        p = _make_csv(
            tmp_path,
            [[SOURCE, SEC, SUB, "INVALID", "", "HC", "S", ""]],
        )
        with pytest.raises(ValueError, match="invalid action"):
            parse_csv(str(p))

    def test_update_without_video_id_raises(self, tmp_path):
        p = _make_csv(
            tmp_path,
            [[SOURCE, SEC, SUB, "update", "Title", "HC", "S", ""]],
        )
        with pytest.raises(ValueError, match="'video ID' is required"):
            parse_csv(str(p))

    def test_keep_with_video_id_raises(self, tmp_path):
        p = _make_csv(
            tmp_path,
            [[SOURCE, SEC, SUB, "keep", "", "HC", "S", VID]],
        )
        with pytest.raises(ValueError, match="'video ID' must be empty"):
            parse_csv(str(p))


# ---------------------------------------------------------------------------
# csv_parser — group_rows
# ---------------------------------------------------------------------------


class TestGroupRows:
    def test_groups_by_source_type_industry(self, tmp_path):
        p = _make_csv(
            tmp_path,
            [
                [SOURCE, SEC, SUB, "update", "Title", "HC", "S", VID],
                [SOURCE, SEC, SUB, "update", "Title", "HC", "L", VID],
                [SOURCE, SEC, SUB, "update", "Title", "MD", "S", VID],
            ],
        )
        rows = parse_csv(str(p))
        groups = group_rows(rows)
        assert len(groups) == 3
        assert (SOURCE, "S", "HC") in groups
        assert (SOURCE, "L", "HC") in groups
        assert (SOURCE, "S", "MD") in groups


# ---------------------------------------------------------------------------
# csv_parser — derive_dest_course_key
# ---------------------------------------------------------------------------


class TestDeriveDestCourseKey:
    def test_key_format(self):
        from opaque_keys.edx.locator import CourseLocator

        source = CourseLocator.from_string("course-v1:UAI_SOURCE+UAI.2+2T2025")
        dest = derive_dest_course_key(source, "S", "HC")
        assert dest.org == "UAI_SOURCE"
        assert dest.course == "UAI.2.S.HC"
        assert dest.run == "2T2025"
        assert str(dest) == "course-v1:UAI_SOURCE+UAI.2.S.HC+2T2025"


# ---------------------------------------------------------------------------
# val_validator
# ---------------------------------------------------------------------------


class TestValidateVideoIds:
    def test_valid_ids(self):
        from ol_openedx_short_video_course.utils.val_validator import validate_video_ids

        class FakeNotFound(Exception):
            pass

        def fake_get_video_info(video_id):
            return {"id": video_id, "status": "ready"}

        api_module = types.ModuleType("edxval.api")
        api_module.ValVideoNotFoundError = FakeNotFound
        api_module.get_video_info = fake_get_video_info

        edxval_module = types.ModuleType("edxval")
        edxval_module.api = api_module

        with patch.dict(
            sys.modules,
            {
                "edxval": edxval_module,
                "edxval.api": api_module,
            },
        ):
            results = validate_video_ids({"valid-id-123"})

        assert results["valid-id-123"] is True

    def test_invalid_id(self):
        from ol_openedx_short_video_course.utils.val_validator import validate_video_ids

        class FakeNotFound(Exception):
            pass

        def fake_get_video_info(video_id):
            raise FakeNotFound(video_id)

        api_module = types.ModuleType("edxval.api")
        api_module.ValVideoNotFoundError = FakeNotFound
        api_module.get_video_info = fake_get_video_info

        edxval_module = types.ModuleType("edxval")
        edxval_module.api = api_module

        with patch.dict(
            sys.modules,
            {
                "edxval": edxval_module,
                "edxval.api": api_module,
            },
        ):
            results = validate_video_ids({"bad-id"})

        assert results["bad-id"] is False

    def test_operational_error_raises(self):
        from ol_openedx_short_video_course.utils.val_validator import validate_video_ids

        class FakeNotFound(Exception):
            pass

        def fake_get_video_info(_video_id):
            raise RuntimeError("VAL timeout")

        api_module = types.ModuleType("edxval.api")
        api_module.ValVideoNotFoundError = FakeNotFound
        api_module.get_video_info = fake_get_video_info

        edxval_module = types.ModuleType("edxval")
        edxval_module.api = api_module

        with (
            patch.dict(
                sys.modules,
                {
                    "edxval": edxval_module,
                    "edxval.api": api_module,
                },
            ),
            pytest.raises(RuntimeError, match="Failed to validate VAL video ID"),
        ):
            validate_video_ids({"some-id"})


class TestCourseValidator:
    def test_reports_missing_source_subsection_coverage(self):
        from ol_openedx_short_video_course.utils.course_validator import (
            validate_all_groups,
        )

        source_course = _FakeBlock(
            "course",
            children=[
                _FakeBlock(
                    "sec1",
                    children=[
                        _FakeBlock("sub1"),
                        _FakeBlock("sub2"),
                    ],
                )
            ],
        )

        class FakeStore:
            def get_course(self, course_key, _depth=None):
                if str(course_key) == SOURCE:
                    return source_course
                return None

        rows = [
            CsvRow(
                source_course_key_str=SOURCE,
                section_key_str=_usage_key("chapter", "sec1"),
                subsection_key_str=_usage_key("sequential", "sub1"),
                action="keep",
                unit_display_name="",
                industry_code="HC",
                type_code="S",
                video_id="",
                line_number=2,
            )
        ]
        groups = {(SOURCE, "S", "HC"): rows}

        with _patch_modulestore(FakeStore()):
            report = validate_all_groups(groups)

        assert report.is_valid is False
        assert any("sub2" in err and "not covered" in err for err in report.errors)


class TestCourseTransformer:
    def test_apply_group_actions_keep_remove_update_and_empty_section_cleanup(self):
        from ol_openedx_short_video_course.utils.course_transformer import (
            apply_group_actions,
        )
        from opaque_keys.edx.keys import CourseKey

        sub_keep = _FakeBlock("sub_keep", children=[_FakeBlock("keep_unit")])
        sub_update = _FakeBlock(
            "sub_update",
            children=[_FakeBlock("old_unit")],
            display_name="Old Subsection",
        )
        sub_remove = _FakeBlock("sub_remove", children=[_FakeBlock("remove_unit")])

        section_with_content = _FakeBlock("sec1", children=[sub_keep, sub_update])
        section_to_remove = _FakeBlock("sec2", children=[sub_remove])
        course = _FakeBlock(
            "course",
            children=[section_with_content, section_to_remove],
        )

        class FakeStore:
            def __init__(self):
                self.deleted_ids: list[str] = []
                self.created: list[tuple[str, str, dict, str]] = []

            def bulk_operations(self, _dest_key):
                return _NullContext()

            def get_course(self, _dest_key, _depth=None):
                return course

            def delete_item(self, location, _user_id):
                self.deleted_ids.append(location.block_id)

            def create_child(self, _user_id, parent_loc, block_type, block_id, fields):
                self.created.append((block_type, block_id, fields, parent_loc.block_id))
                return _FakeBlock(
                    block_id,
                    display_name=fields.get("display_name", ""),
                )

        rows = [
            CsvRow(
                source_course_key_str=SOURCE,
                section_key_str=_usage_key("chapter", "sec1"),
                subsection_key_str=_usage_key("sequential", "sub_keep"),
                action="keep",
                unit_display_name="",
                industry_code="HC",
                type_code="S",
                video_id="",
                line_number=2,
            ),
            CsvRow(
                source_course_key_str=SOURCE,
                section_key_str=_usage_key("chapter", "sec1"),
                subsection_key_str=_usage_key("sequential", "sub_update"),
                action="update",
                unit_display_name="New Unit",
                industry_code="HC",
                type_code="S",
                video_id=VID,
                line_number=3,
            ),
            CsvRow(
                source_course_key_str=SOURCE,
                section_key_str=_usage_key("chapter", "sec2"),
                subsection_key_str=_usage_key("sequential", "sub_remove"),
                action="remove",
                unit_display_name="",
                industry_code="HC",
                type_code="S",
                video_id="",
                line_number=4,
            ),
        ]

        fake_store = FakeStore()
        with _patch_modulestore(fake_store):
            result = apply_group_actions(
                CourseKey.from_string(SOURCE),
                rows,
                user_id=7,
            )

        assert result.kept == 1
        assert result.updated == 1
        assert result.removed == 1
        assert result.empty_sections_removed == 1
        assert "sub_remove" in fake_store.deleted_ids
        assert "old_unit" in fake_store.deleted_ids
        assert "sec2" in fake_store.deleted_ids
        assert any(
            created[0] == "vertical" and created[1] == "svg_sub_update_unit"
            for created in fake_store.created
        )
        assert any(
            created[0] == "video" and created[1] == "svg_sub_update_video"
            for created in fake_store.created
        )


class TestServices:
    def test_dry_run_returns_plan_and_skips_writes(self):
        from ol_openedx_short_video_course.utils.course_validator import (
            ValidationReport,
        )

        from ol_openedx_short_video_course import services

        rows = [
            CsvRow(
                source_course_key_str=SOURCE,
                section_key_str=_usage_key("chapter", "sec1"),
                subsection_key_str=_usage_key("sequential", "sub1"),
                action="keep",
                unit_display_name="",
                industry_code="HC",
                type_code="S",
                video_id="",
                line_number=2,
            )
        ]
        groups = {(SOURCE, "S", "HC"): rows}

        with (
            patch.object(services, "parse_csv", return_value=rows),
            patch.object(services, "group_rows", return_value=groups),
            patch.object(services, "validate_video_ids", return_value={}),
            patch.object(
                services, "validate_all_groups", return_value=ValidationReport()
            ),
            patch.object(services, "prepare_destination") as mock_prepare,
            patch.object(services, "apply_group_actions") as mock_apply,
        ):
            result = services.generate_custom_courses(
                csv_path="/tmp/mapping.csv",
                user_id=99,
                dry_run=True,
            )

        assert result.success is True
        assert result.dry_run is True
        assert len(result.planned_ops) == 1
        mock_prepare.assert_not_called()
        mock_apply.assert_not_called()

    def test_validation_failure_short_circuits_before_writes(self):
        from ol_openedx_short_video_course.utils.course_validator import (
            ValidationReport,
        )

        from ol_openedx_short_video_course import services

        rows = [
            CsvRow(
                source_course_key_str=SOURCE,
                section_key_str=_usage_key("chapter", "sec1"),
                subsection_key_str=_usage_key("sequential", "sub1"),
                action="keep",
                unit_display_name="",
                industry_code="HC",
                type_code="S",
                video_id="",
                line_number=2,
            )
        ]
        groups = {(SOURCE, "S", "HC"): rows}

        with (
            patch.object(services, "parse_csv", return_value=rows),
            patch.object(services, "group_rows", return_value=groups),
            patch.object(
                services,
                "validate_all_groups",
                return_value=ValidationReport(errors=["boom"]),
            ),
            patch.object(services, "prepare_destination") as mock_prepare,
            patch.object(services, "apply_group_actions") as mock_apply,
        ):
            result = services.generate_custom_courses(
                csv_path="/tmp/mapping.csv",
                user_id=99,
                dry_run=False,
            )

        assert result.success is False
        assert result.validation_errors == ["boom"]
        assert result.run_results == []
        mock_prepare.assert_not_called()
        mock_apply.assert_not_called()
