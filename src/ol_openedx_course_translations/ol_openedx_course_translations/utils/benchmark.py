"""
The benchmark block, and the measurements taken over it.

Shared by the management command and the Celery tasks it dispatches, so the
tasks need not import the command.
"""

from dataclasses import dataclass

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import UsageKey

from ol_openedx_course_translations.utils.course_translations import (
    HtmlXmlTranslationHelper,
)

# An html block's body is a fragment with no single root, and production
# translates such content as HTML — tasks.py picks tag_handling from the file
# suffix. Parsing it as XML would reject the very content the benchmark exists
# to measure.
BENCHMARK_TAG_HANDLING = "html"


class BenchmarkError(Exception):
    """The benchmark block is missing, unreadable, or has nothing to translate."""


@dataclass(frozen=True)
class Benchmark:
    """One course block's body, read and parsed once per task."""

    block_id: str
    display_name: str
    content: str
    # Stripped source unit texts, for the unchanged-unit count.
    units: frozenset[str]


def units_and_elements(markup: str) -> tuple[list[str], int]:
    """Extract translatable units and count elements, for the arm checks."""
    helper = HtmlXmlTranslationHelper(is_xml=False)
    try:
        root = helper.parse(markup)
    except AttributeError:
        # edx-platform's defuse_xml_libs() replaces lxml.etree wholesale, and
        # its fromstring calls .getroottree() on the parse result — so inside
        # the platform an element-free document raises here where bare lxml
        # returns None. Both mean the same thing and neither is this run's
        # fault, so both are "nothing to translate".
        return [], 0
    if root is None:
        # No element node at all: a lone comment, DOCTYPE, PI or CDATA
        # section. Reported rather than left to raise deeper in.
        return [], 0
    root, units, _ = helper.extract_units(markup)
    # Comments and processing instructions have non-string tags; counting them
    # would make a validator that touches a comment look like one that
    # restructured the document.
    return units, sum(1 for node in root.iter() if isinstance(node.tag, str))


def read_benchmark(block_id: str) -> Benchmark:
    """
    Load a course block's body and parse it.

    The command calls this before anything is spent, so an unusable block is
    reported as the cause rather than surfacing later as every translator
    appearing to fail.

    Reads the published revision: it is what a course export contains, so the
    benchmark measures the same text ``translate_course`` would process, and
    it does not shift under an author editing in Studio mid-run.
    """
    # Imported here because xmodule exists only inside edx-platform, and this
    # module has to stay importable for the host test suite.
    from xmodule.modulestore import ModuleStoreEnum  # noqa: PLC0415
    from xmodule.modulestore.django import modulestore  # noqa: PLC0415
    from xmodule.modulestore.exceptions import ItemNotFoundError  # noqa: PLC0415

    try:
        usage_key = UsageKey.from_string(block_id)
    except InvalidKeyError as error:
        msg = f"{block_id!r} is not a usage key: {error}"
        raise BenchmarkError(msg) from error

    try:
        block = modulestore().get_item(
            usage_key, revision=ModuleStoreEnum.RevisionOption.published_only
        )
    except (ItemNotFoundError, AssertionError) as error:
        # AssertionError: a v2 library key (lb:...) is a valid UsageKey but
        # MixedModuleStore asserts on it rather than raising something useful.
        msg = f"No published block at {block_id} ({type(error).__name__})."
        raise BenchmarkError(msg) from error

    if usage_key.block_type != "html":
        # A problem block also has .data, but it exports as .xml and
        # production translates it as XML — benchmarking it as HTML would
        # measure the very mismatch BENCHMARK_TAG_HANDLING exists to avoid.
        msg = (
            f"Block {block_id} is a {usage_key.block_type} block; "
            f"only html blocks can be benchmarked."
        )
        raise BenchmarkError(msg)

    content = getattr(block, "data", None)
    if not isinstance(content, str) or not content.strip():
        # An html block whose body was never filled in, or was emptied.
        msg = f"Block {block_id} has no markup body to translate."
        raise BenchmarkError(msg)

    # No parse guard: lxml's HTML parser recovers from anything, including
    # unclosed tags and stray angle brackets. Emptiness is the only input it
    # cannot handle, and that is caught above.
    units, _ = units_and_elements(content)
    if not units:
        # Otherwise this reaches the arms and is blamed on every translator in
        # turn, after the run has paid for a translation each.
        msg = f"Block {block_id} has no translatable text."
        raise BenchmarkError(msg)

    return Benchmark(
        block_id=block_id,
        display_name=getattr(block, "display_name", "") or usage_key.block_id,
        content=content,
        units=frozenset(unit.strip() for unit in units),
    )


def count_unchanged_units(markup: str, benchmark: Benchmark) -> int:
    """
    Count units whose text still matches some source unit.

    A diagnostic in the report only; the translate task's arm gate applies
    the same rule to the units it already holds. Always a number: content the
    parser cannot find an element in yields no units, and so counts zero
    rather than being unmeasurable.
    """
    units, _ = units_and_elements(markup)
    # Currently a no-op on both sides: extract_units returns text whose outer
    # whitespace _split_preserve_outer_ws has already removed. Kept as the
    # only thing decoupling this comparison from that, not because any input
    # reaching it needs stripping.
    return sum(1 for unit in units if unit.strip() in benchmark.units)
