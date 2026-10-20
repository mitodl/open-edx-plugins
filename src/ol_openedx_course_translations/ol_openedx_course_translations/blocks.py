"""
Which text of each block type is translated, and which stays in the course language.

Rule: translate what the learner reads; never translate a value that is itself the
answer (saved as the learner's response, or compared when grading). Options saved
by id or key are translated, since the saved answer does not change.
"""

import copy
import json

from lxml import etree

TRANSLATABLE_BLOCK_FIELDS = {
    "about": ("data",),
    "annotatable": ("display_name", "data"),
    "chapter": ("display_name",),
    "course": ("display_name",),
    "course_info": ("data", "items"),
    "discussion": ("display_name",),
    "done": ("display_name",),
    "drag-and-drop-v2": ("display_name", "question_text", "data"),
    "edx_sga": ("display_name",),
    "google-calendar": ("display_name",),
    "google-document": ("display_name", "alt_text"),
    "html": ("display_name", "data"),
    "lti": ("display_name", "description", "button_text"),
    "lti_consumer": ("display_name", "description", "button_text"),
    "ol_openedx_chat_xblock": ("display_name",),
    "openassessment": (
        "display_name",
        "title",
        "prompt",
        "rubric_criteria",
        "rubric_feedback_prompt",
    ),
    "poll": ("display_name", "question", "feedback", "answers"),
    "poll_question": ("display_name", "question", "answers"),
    "problem": ("display_name", "data"),
    "scorm": ("display_name", "navigation_menu"),
    "sequential": ("display_name",),
    "staffgradedxblock": ("display_name", "instructions"),
    "static_tab": ("display_name", "data"),
    "survey": ("display_name", "block_name", "feedback", "questions", "answers"),
    "vertical": ("display_name",),
    "video": ("display_name",),
    "word_cloud": ("display_name", "instructions"),
}

# Handlers that must see the source text. ORA hashes the whole rubric (labels and
# prompts included) when an assessment is created; lti_consumer sends its
# display_name to the external tool.
SOURCE_TEXT_HANDLERS = {
    "openassessment": {
        "assessment",
        "peer_assess",
        "self_assess",
        "staff_assess",
        "submit",
        "training_assess",
    },
    "lti_consumer": {"lti_launch_handler"},
}

# Blocks whose learners type free text, which is kept in the course language.
ANSWER_NOTE_FIELDS = {"openassessment": "prompt"}
TYPED_ANSWER_TAGS = (
    "coderesponse",
    "customresponse",
    "optionresponse",
    "stringresponse",
    "symbolicresponse",
)

# Keys of structured fields (drag and drop data, rubrics, polls, updates) that are
# ids, configuration or URLs rather than text.
KEEP_KEYS = {
    "align",
    "date",
    "feedback",  # ORA criterion: "optional" / "required"
    "id",
    "img",
    "imageURL",
    "item_background_color",
    "item_text_color",
    "key",
    "max_items_per_zone",
    "mode",
    "name",
    "order_num",
    "points",
    "status",
    "targetImg",
    "uid",
    "url",
    "zone",
}

# Capa: attributes and elements that hold answers, grading code or configuration.
CAPA_KEEP_ATTRIBUTES = {
    "allowed_files",
    "analyses",
    "answer",
    "answer-pool",
    "cfn",
    "cfn_extra_args",
    "choice",
    "correct",
    "default",
    "dojs",
    "empty_answer_err",
    "expect",
    "explanation-id",
    "fixed",
    "geometries",
    "get_statefn",
    "gradefn",
    "height",
    "hintfn",
    "html_file",
    "id",
    "img",
    "initial_state",
    "initial_value",
    "inline",
    "math",
    "mode",
    "molecules",
    "multiple_inputtypes",
    "name",
    "on",
    "one_per_target",
    "options",
    "params",
    "partial_answers",
    "partial_credit",
    "partial_range",
    "parts",
    "point_value",
    "preprocessorClassName",
    "preprocessorSrc",
    "queuename",
    "rectangle",
    "regions",
    "required_files",
    "samples",
    "selected",
    "set_statefn",
    "show_correctness",
    "shuffle",
    "size",
    "sop",
    "src",
    "submit_analyses",
    "target_outline",
    "target_shape",
    "tests",
    "tolerance",
    "type",
    "url",
    "value",
    "width",
}
# Whole subtree kept: grading code, math and legacy drag-and-drop labels.
CAPA_KEEP_SUBTREES = {
    "answer",
    "codeparam",
    "draggable",
    "grader_payload",
    "math",
    "responseparam",
    "script",
    "target",
}
# Only the element's own text kept: dropdown options are saved as their text.
CAPA_KEEP_TEXT = {"additional_answer", "option"}


def serialize(value):
    """Return a field value as stored in ``BlockTranslation.translated_value``."""
    if value is None or isinstance(value, str):
        return value or ""
    return json.dumps(value, sort_keys=True)


def deserialize(source_value, stored):
    """Turn a stored translation back into the field's own type."""
    if source_value is None or isinstance(source_value, str):
        return stored
    return json.loads(stored)


def restore_kept_parts(block_type, field, source_value, translated_value):
    """
    Return the translated value with every kept part copied from the source.

    Returns ``None`` when the two values cannot be matched up safely.
    """
    if block_type == "problem" and field == "data":
        return restore_capa(source_value, translated_value)
    if isinstance(source_value, str) or source_value is None:
        return translated_value
    try:
        return _restore_structure(source_value, json.loads(translated_value))
    except (TypeError, ValueError, _MismatchError):
        return None


class _MismatchError(Exception):
    """The translated value does not have the source's shape."""


def _restore_structure(source, translated, key=None):
    if type(source) is not type(translated):
        raise _MismatchError
    if isinstance(source, dict):
        return _restore_dict(source, translated, key)
    if isinstance(source, list):
        return _restore_list(source, translated, key)
    return translated if isinstance(source, str) else source


def _restore_dict(source, translated, key):
    if set(source) - set(translated):
        raise _MismatchError
    result = {}
    for name, value in source.items():
        keep = (
            name in KEEP_KEYS
            # A drag item's allowed zones are uids; the course's zones are dicts.
            or (name == "zones" and all(isinstance(zone, str) for zone in value))
            # Drag and drop v1 data uses a zone's title as its uid.
            or (name == "title" and key == "zones" and "uid" not in source)
        )
        result[name] = (
            copy.deepcopy(value)
            if keep
            else _restore_structure(value, translated[name], name)
        )
    return result


def _restore_list(source, translated, key):
    if len(source) != len(translated):
        raise _MismatchError
    # Poll and survey pairs are [key, label-or-details].
    pair = len(source) == 2 and isinstance(source[0], str)  # noqa: PLR2004
    return [
        value if pair and index == 0 else _restore_structure(value, other, key)
        for index, (value, other) in enumerate(zip(source, translated, strict=True))
    ]


def restore_capa(source_xml, translated_xml):
    """
    Return the translated problem XML with every kept part copied from the source.

    Returns ``None`` when the two documents do not have the same element
    structure, because then parts cannot be matched up safely.
    """
    try:
        source = etree.fromstring(source_xml)
        translated = etree.fromstring(translated_xml)
    except (etree.XMLSyntaxError, ValueError):
        return None
    source_nodes = list(source.iter())
    translated_nodes = list(translated.iter())
    if [node.tag for node in source_nodes] != [node.tag for node in translated_nodes]:
        return None
    kept = {
        node
        for root in source_nodes
        if root.tag in CAPA_KEEP_SUBTREES
        for node in root.iter()
    }
    for source_node, translated_node in zip(
        source_nodes, translated_nodes, strict=True
    ):
        if source_node in kept:
            translated_node.attrib.clear()
            translated_node.attrib.update(source_node.attrib)
            translated_node.text = source_node.text
            if source_node.getparent() in kept:
                translated_node.tail = source_node.tail
            continue
        for attribute in CAPA_KEEP_ATTRIBUTES & set(source_node.attrib):
            translated_node.set(attribute, source_node.get(attribute))
        if source_node.tag in CAPA_KEEP_TEXT:
            translated_node.text = source_node.text
    return etree.tostring(translated, encoding="unicode")
