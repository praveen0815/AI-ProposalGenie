"""Document storage backends."""

from app.storage.base import DocumentStorage, StorageError
from app.storage.local import LocalDocumentStorage

__all__ = ["DocumentStorage", "LocalDocumentStorage", "StorageError"]
