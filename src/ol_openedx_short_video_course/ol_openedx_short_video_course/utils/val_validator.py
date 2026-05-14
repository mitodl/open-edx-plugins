"""VAL (edX Video Abstraction Layer) video ID validation."""

import logging

log = logging.getLogger(__name__)


def validate_video_ids(video_ids: set[str]) -> dict[str, bool]:
    """
    Check each video ID against VAL.

    Returns a dict mapping video_id → is_valid.
    Imports edxval at call time so the module can be imported without it installed.
    """
    try:
        from edxval.api import ValVideoNotFoundError, get_video_info  # noqa: PLC0415
    except ImportError:
        msg = (
            "edxval is not installed or importable; cannot validate VAL video IDs. "
            "Install/configure edxval and retry."
        )
        log.exception(msg)
        raise RuntimeError(msg) from None

    results: dict[str, bool] = {}
    for video_id in video_ids:
        if not video_id:
            results[video_id] = False
            continue
        try:
            get_video_info(video_id)
            results[video_id] = True
        except ValVideoNotFoundError:
            results[video_id] = False
        except Exception as exc:
            log.exception("Error while validating video ID '%s' against VAL", video_id)
            msg = (
                f"Failed to validate VAL video ID '{video_id}' "
                "due to an operational error"
            )
            raise RuntimeError(msg) from exc

    return results
