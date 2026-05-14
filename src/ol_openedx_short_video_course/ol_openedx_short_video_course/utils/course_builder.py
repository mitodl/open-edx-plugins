"""Course cloning (preparation) utilities."""

import logging

from opaque_keys.edx.keys import CourseKey

log = logging.getLogger(__name__)


def prepare_destination(
    source_key: CourseKey,
    dest_key: CourseKey,
    user_id: int,
) -> None:
    """
    Clone *source_key* into *dest_key*.

    Raises ValueError if the destination course already exists — callers
    should check this before entering a batch to avoid partial writes.
    """
    from xmodule.modulestore.django import modulestore  # noqa: PLC0415

    store = modulestore()

    if store.get_course(dest_key) is not None:
        msg = (
            f"Destination course already exists: '{dest_key}'. "
            "Pre-flight validation should have caught this; aborting."
        )
        raise ValueError(msg)

    log.info("Cloning %s → %s", source_key, dest_key)
    store.clone_course(source_key, dest_key, user_id)
    log.info("Clone complete: %s", dest_key)
