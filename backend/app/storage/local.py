"""Local filesystem storage for development."""

from pathlib import Path, PurePosixPath

from app.storage.base import StorageError


class LocalDocumentStorage:
    """Stores documents under a private root using server-generated relative keys."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    def save(self, key: str, data: bytes) -> None:
        destination = self._resolve(key)
        temporary = destination.with_name(f"{destination.name}.partial")
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_bytes(data)
            temporary.replace(destination)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise StorageError("The document could not be stored") from exc

    def read(self, key: str) -> bytes:
        source = self._resolve(key)
        try:
            return source.read_bytes()
        except FileNotFoundError as exc:
            raise StorageError("The stored file is missing") from exc
        except OSError as exc:
            raise StorageError("The stored file could not be read") from exc

    def delete(self, key: str) -> None:
        target = self._resolve(key)
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError("The stored file could not be deleted") from exc

    def _resolve(self, key: str) -> Path:
        if not key or "\\" in key or key.startswith("/"):
            raise StorageError("Invalid storage key")
        relative = PurePosixPath(key)
        if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
            raise StorageError("Invalid storage key")
        destination = self.root.joinpath(*relative.parts).resolve()
        if not destination.is_relative_to(self.root):
            raise StorageError("Invalid storage key")
        return destination
