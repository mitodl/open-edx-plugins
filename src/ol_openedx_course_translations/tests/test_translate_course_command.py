"""translate_course: the prompt, and when the log row is written."""

import io
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError
from ol_openedx_course_translations.management.commands import translate_course
from ol_openedx_course_translations.models import CourseTranslationLog

SOURCE = "course-v1:QA+T+2026"
TARGET = "course-v1:QA+T.FR+2026"
STEPS = (
    "confirm",
    "_validate_source_course",
    "_export_source_course",
    "_translate_course_content_async",
    "_wait_and_report_tasks",
    "_write_translations_meta_file",
    "_import_translated_course",
)


@pytest.fixture
def steps(tmp_path):
    """The command with every step that touches the modulestore or Celery mocked."""
    with (
        mock.patch.multiple(
            translate_course.Command, **dict.fromkeys(STEPS, mock.DEFAULT)
        ) as mocks,
        mock.patch.object(
            translate_course, "create_translated_copy", return_value=tmp_path
        ),
        mock.patch.object(
            translate_course,
            "parse_and_validate_provider_spec",
            return_value=("openai", "gpt-5.2"),
        ),
    ):
        mocks["_export_source_course"].return_value = tmp_path / "export"
        mocks["_wait_and_report_tasks"].return_value = ["done"]
        yield mocks


def run(**options):
    out = io.StringIO()
    call_command(
        "translate_course",
        source_course_id=SOURCE,
        target_course_id=TARGET,
        target_language="fr",
        content_translation_provider="openai",
        srt_translation_provider="openai",
        stdout=out,
        **options,
    )
    return out.getvalue()


@pytest.mark.django_db
def test_yes_skips_the_prompt_and_logs_the_imported_course(steps):
    run(yes=True)

    steps["confirm"].assert_not_called()
    log = CourseTranslationLog.objects.get(source_course_id=SOURCE)
    assert f"Target course: {TARGET}" in log.command_stats


@pytest.mark.django_db
def test_a_failed_import_leaves_no_log_row(steps):
    steps["_import_translated_course"].side_effect = RuntimeError("import failed")

    with pytest.raises(CommandError, match="import failed"):
        run(yes=True)

    assert not CourseTranslationLog.objects.exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("steps")
def test_a_failed_log_write_does_not_fail_an_imported_course():
    with mock.patch.object(
        CourseTranslationLog.objects, "create", side_effect=DatabaseError("db down")
    ):
        output = run(yes=True)

    assert "the translation log write failed" in output
    assert "Translation completed successfully" in output
