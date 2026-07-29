"""Shared test doubles for ol_openedx_canvas_integration tests."""

from __future__ import annotations


class MockSubsection:
    """Minimal subsection object used for Canvas assignment payload tests."""

    def __init__(
        self, location: str, display_name: str = "Mock subsection", due=None
    ) -> None:
        """Initialize subsection location, name, and optional due date."""
        self.location = location
        self.display_name = display_name
        self.fields: dict = {"due": due} if due else {}


class HashableUser:
    """Minimal user stub with stable hashing for dict-key usage in tests."""

    def __init__(self, email: str, user_id=None) -> None:
        """Store email and optional id fields used by task/api logic."""
        self.email = email
        self.id = user_id

    def __hash__(self) -> int:
        """Hash by id and email for deterministic key behavior."""
        return hash((self.id, self.email))

    def __eq__(self, other) -> bool:
        """Compare HashableUser instances by id and email."""
        return (
            isinstance(other, HashableUser)
            and self.id == other.id
            and self.email == other.email
        )


def stub_canvas_client_factory(stub_client):
    """Return a CanvasClient-shaped factory that always returns stub_client."""

    def _factory(**_kwargs):
        return stub_client

    return _factory
