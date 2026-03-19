# ruff: noqa: E501
"""Utility methods for the AI chat"""

import json
import logging
import re

from lms.djangoapps.courseware.courses import get_course_by_id
from opaque_keys.edx.locator import CourseLocator

try:
    from xmodule.video_block.transcripts_utils import (
        Transcript,
        get_available_transcript_languages,
    )
except ImportError:
    from openedx.core.djangoapps.video_config.transcripts_utils import (
        Transcript,
        get_available_transcript_languages,
    )

from ol_openedx_chat.constants import (
    BLOCK_TYPE_TO_SETTINGS,
    CHAT_APPLICABLE_BLOCKS,
    ENGLISH_LANG_CODE,
)

log = logging.getLogger(__name__)


def is_aside_applicable_to_block(block):
    """Check if the xBlock should support AI Chat"""
    return getattr(block, "category", None) in CHAT_APPLICABLE_BLOCKS


def get_course(block):
    """
    Get the course for a given block.

    Args:
        block (XBlock): The block for which to get the course.

    Returns:
        Course: The course for the given block, or None if the course cannot be found.
    """
    # During course import, the course_key uses older format `{org}/{course}/{run}`
    # as explained in `https://github.com/openedx/edx-platform/blob/8ad4d081fbdc024ed08cd1477380b395d78bb051/common/lib/xmodule/xmodule/modulestore/xml.py#L573`.
    # We convert it to the latest course key if course_id is deprecated/old format.
    course_id = block.usage_key.course_key
    if course_id.deprecated:
        course_id = CourseLocator(course_id.org, course_id.course, course_id.run)

    try:
        return get_course_by_id(course_id)
    except Exception:
        log.exception("Couldn't fetch course for block with id %s", block.location)
        return None


def is_ol_chat_enabled_for_course(block):
    """
    Return whether OL Chat is enabled or not for a block type in a course

    Args:
        block (ProblemBlock or VideoBlock): The block for which to check if OL Chat is enabled

    Returns:
        bool: True if OL Chat is enabled, False otherwise
    """
    course = get_course(block)
    # Sometimes we cannot find a course by the ID i.e. during course import.
    # We return True in that case to avoid breaking the import process.
    # This will work fine with LMS and CMS.
    if not course:
        return True

    other_course_settings = course.other_course_settings
    block_type = getattr(block, "category", None)
    return other_course_settings.get(BLOCK_TYPE_TO_SETTINGS.get(block_type))


def get_checkpoint_and_thread_id(content):
    """
    Extract the checkpoint ID and thread ID from chat response content.

    Args:
        content (str): The content from the chat response.
    Returns:
        tuple: A tuple containing the thread ID and checkpoint PK, or (None, None)
                if extraction fails.
    """
    if content is None:
        return None, None
    try:
        # Decode bytes to string
        content_str = content.decode("utf-8") if isinstance(content, bytes) else content
        # The content from the chat response contains values with JSON data.
        # e.g. It looks like '_content': b'Hello! How can I help you?\n\n
        # <!-- {"checkpoint_pk": 123, "thread_id": "abc123"} -->\n\n'
        match = re.search(r"<!-- ({.*}) -->", content_str)
        if match:
            dict_values = json.loads(match.group(1))
            return dict_values.get("thread_id", None), str(
                dict_values.get("checkpoint_pk", None)
            )
    except Exception:
        log.exception(
            "Couldn't parse content/suffix to get Thread_id and Checkpoint_pk."
            " content: %s",
            content,
        )
    return None, None


def get_transcript_asset_id(block):
    """
    Get the transcript asset ID for a video block.

    Args:
        block (VideoBlock): The video block for which to get the transcript asset ID.

    Returns:
        str: The transcript asset ID if available, otherwise None.
    """
    course = get_course(block)
    course_language = LanguageCode(course.language).to_bcp47()
    try:
        transcripts_info = block.get_transcripts_info()
        transcripts = transcripts_info.get("transcripts", {})
        if transcripts and transcripts.get(course_language):
            return Transcript.asset_location(
                block.location,
                transcripts_info["transcripts"][course_language],
            )

        transcript_languages = get_available_transcript_languages(block.edx_video_id)
        if course_language in transcript_languages:
            return Transcript.asset_location(
                block.location,
                f"{block.edx_video_id}-{course_language}.srt",
            )

        # Fallback to English transcript if available.
        if transcripts and transcripts.get(ENGLISH_LANG_CODE):
            return Transcript.asset_location(
                block.location,
                transcripts_info["transcripts"][ENGLISH_LANG_CODE],
            )

        if ENGLISH_LANG_CODE in transcript_languages:
            return Transcript.asset_location(
                block.location,
                f"{block.edx_video_id}-{ENGLISH_LANG_CODE}.srt",
            )

    except Exception:  # noqa: BLE001
        log.info(
            "Error while fetching transcripts for block %s",
            block.location,
        )


class LanguageCode:
    """
    Utility class for handling language code conversions between
    Django/Open edX style and BCP47.
    """

    def __init__(self, lang_code):
        self.lang_code = lang_code

    def to_bcp47(self) -> str:
        """
        Convert Django / Open edX style language codes to BCP47.

        Examples:
            zh_HANS     -> zh-Hans
            zh_HANT     -> zh-Hant
            zh_HANS_CN  -> zh-Hans-CN
            en_US       -> en-US
            es_419      -> es-419
            pt_br       -> pt-BR
        """
        if not self.lang_code:
            return self.lang_code

        parts = self.lang_code.replace("_", "-").split("-")
        result = []
        for idx, part in enumerate(parts):
            if idx == 0:
                # Language
                result.append(part.lower())

            elif re.fullmatch(r"[A-Za-z]{4}", part):
                # Script (Hans, Hant, Latn, Cyrl, etc.)
                result.append(part.title())

            elif re.fullmatch(r"[A-Za-z]{2}", part):
                # Region i.e US, PK, CN
                result.append(part.upper())

            elif re.fullmatch(r"\d{3}", part):
                # Numeric region (419)
                result.append(part)

            else:
                # Variants/extensions
                result.append(part.lower())

        return "-".join(result)

    def to_django(self) -> str:
        """
        Convert BCP47 language tags to Django / Open edX style.

        Examples:
            zh-Hans     -> zh_HANS
            zh-Hant     -> zh_HANT
            zh-Hans-CN  -> zh_HANS_CN
            en-US       -> en_US
            es-419      -> es_419
            pt-BR       -> pt_BR
        """
        if not self.lang_code:
            return self.lang_code

        parts = self.lang_code.replace("_", "-").split("-")
        result = []

        for idx, part in enumerate(parts):
            if idx == 0:
                # Language
                result.append(part.lower())

            elif re.fullmatch(r"[A-Za-z]{4}", part):
                # Script
                result.append(part.upper())

            elif re.fullmatch(r"[A-Za-z]{2}", part):
                # Region
                result.append(part.upper())

            elif re.fullmatch(r"\d{3}", part):
                # Numeric region
                result.append(part)

            else:
                # Variants/extensions
                result.append(part.lower())

        return "_".join(result)
