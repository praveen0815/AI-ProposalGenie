"""Local document storage stays inside its root."""

from pathlib import Path

import pytest

from app.storage.base import StorageError
from app.storage.local import LocalDocumentStorage


def test_round_trip_uses_the_relative_key(tmp_path: Path) -> None:
    storage = LocalDocumentStorage(tmp_path / "documents")
    storage.save("company/document/file.txt", b"hello")

    assert storage.read("company/document/file.txt") == b"hello"
    stored = tmp_path / "documents" / "company" / "document" / "file.txt"
    assert stored.is_file()
    storage.delete("company/document/file.txt")
    assert not stored.exists()
    storage.delete("company/document/file.txt")


@pytest.mark.parametrize(
    "key",
    ["../secrets.txt", "..\\secrets.txt", "/etc/passwd", "company/../../secrets.txt", "", "company/../file.txt"],
)
def test_keys_cannot_escape_the_root(tmp_path: Path, key: str) -> None:
    storage = LocalDocumentStorage(tmp_path / "documents")
    outside = tmp_path / "secrets.txt"

    with pytest.raises(StorageError):
        storage.save(key, b"nope")
    with pytest.raises(StorageError):
        storage.read(key)

    assert not outside.exists()


def test_save_error_does_not_include_the_filesystem_path(tmp_path: Path) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("occupied", encoding="utf-8")
    storage = LocalDocumentStorage(blocker)

    with pytest.raises(StorageError) as caught:
        storage.save("company/document/file.txt", b"hello")

    assert "not-a-directory" not in str(caught.value)
    assert str(tmp_path) not in str(caught.value)
