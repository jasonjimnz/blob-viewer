"""Storage backends.

A backend provides read-only listing/download for remote workspaces (S3) and
full read/write for local workspaces.  Every backend works with the same
object model so the API and UI don't need to care where files live.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Iterator


@dataclass(frozen=True)
class BlobEntry:
    """One file or one common-prefix inside a workspace."""

    key: str
    size: int
    last_modified: float | None
    etag: str | None
    is_dir: bool = False


class StorageError(Exception):
    pass


class NotFoundError(StorageError):
    pass


class ReadOnlyError(StorageError):
    pass


class Storage:
    """Interface implemented by every backend."""

    def list_objects(self, prefix: str = "", delimiter: str = "/") -> tuple[list[BlobEntry], list[BlobEntry]]:
        """Return (files, directories) under *prefix*."""
        raise NotImplementedError

    def get(self, key: str) -> BlobEntry:
        """Metadata for a single object."""
        raise NotImplementedError

    def open(self, key: str) -> BinaryIO:
        """Open a readable binary stream for *key*."""
        raise NotImplementedError

    def download_to(self, key: str, dest_path: str) -> BlobEntry:
        raise NotImplementedError

    def iter_file(self, key: str, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
        raise NotImplementedError

    # -- write operations (local workspaces only) ---------------------------

    def write_file(self, key: str, data: bytes) -> BlobEntry:
        raise ReadOnlyError("This workspace is read-only")

    def delete(self, key: str) -> None:
        raise ReadOnlyError("This workspace is read-only")

    def create_folder(self, key: str) -> None:
        raise ReadOnlyError("This workspace is read-only")

    def rename(self, key: str, new_key: str) -> None:
        raise ReadOnlyError("This workspace is read-only")

    def test_connection(self) -> dict:
        raise NotImplementedError
