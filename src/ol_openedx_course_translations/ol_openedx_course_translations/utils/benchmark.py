"""
The benchmark document, and the measurements taken over it.

Shared by the management command and the Celery tasks it dispatches, so that
neither imports the other.
"""

from dataclasses import dataclass
from pathlib import Path

import ol_openedx_course_translations
from ol_openedx_course_translations.utils.course_translations import (
    HtmlXmlTranslationHelper,
)

BENCHMARK_PATH = (
    Path(ol_openedx_course_translations.__file__).parent
    / "benchmarks"
    / "benchmark_course_content.xml"
)


class BenchmarkError(Exception):
    """The benchmark document is missing, empty, or not well-formed."""


@dataclass(frozen=True)
class Benchmark:
    """The benchmark content, read and parsed once per run."""

    content: str
    # Stripped source unit texts, for the unchanged-unit diagnostic.
    units: frozenset[str]
    elements: int


def units_and_elements(markup: str) -> tuple[list[str], int]:
    """Extract translatable units and count elements, for the arm checks."""
    helper = HtmlXmlTranslationHelper(is_xml=True)
    root, units, _ = helper.extract_units(markup)
    # Comments and processing instructions have non-string tags; counting them
    # would make a validator that touches a comment look like one that
    # restructured the document.
    return units, sum(1 for node in root.iter() if isinstance(node.tag, str))


def read_benchmark() -> Benchmark:
    """
    Read and parse the benchmark before anything is spent.

    Parsing here means a malformed fixture is reported as the cause, rather
    than surfacing later as every translator appearing to fail.
    """
    if not BENCHMARK_PATH.exists():
        msg = f"Benchmark file is missing: {BENCHMARK_PATH}"
        raise BenchmarkError(msg)
    content = BENCHMARK_PATH.read_text(encoding="utf-8")
    if not content.strip():
        msg = f"Benchmark file is empty: {BENCHMARK_PATH}"
        raise BenchmarkError(msg)
    try:
        units, elements = units_and_elements(content)
    except Exception as error:
        msg = f"Benchmark file is not well-formed XML ({BENCHMARK_PATH}): {error}"
        raise BenchmarkError(msg) from error
    return Benchmark(
        content=content,
        units=frozenset(unit.strip() for unit in units),
        elements=elements,
    )


def count_unchanged_units(markup: str, benchmark: Benchmark) -> int | None:
    """
    Count units whose text still matches some source unit.

    Diagnostic only, so a parse failure returns None rather than discarding an
    arm whose content is otherwise scoreable.
    """
    try:
        units, _ = units_and_elements(markup)
    except Exception:  # noqa: BLE001
        return None
    return sum(1 for unit in units if unit.strip() in benchmark.units)
