"""Storage contract for company documents.

A later object-storage backend can implement the same three operations.
Services depend on this protocol, not on a filesystem path.
"""

from typing import Protocol


class StorageError(Exception):
    """The storage backend could not complete an operation."""


class DocumentStorage(Protocol):
    def save(self, key: str, data: bytes) -> None:
        """Store bytes at a relative key."""

    def read(self, key: str) -> bytes:
        """Return the bytes stored at a relative key."""

    def delete(self, key: str) -> None:
        """Remove a stored object. Missing objects are not an error."""
