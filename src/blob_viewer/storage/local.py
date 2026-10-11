"""Local filesystem backend — private, writable workspaces."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import BinaryIO, Iterator

from .base import BlobEntry, NotFoundError, ReadOnlyError, Storage, StorageError


class LocalStorage(Storage):
    """Storage bound to a local folder.  Writable unless marked read-only."""

    def __init__(self, root: str, read_only: bool = False) -> None:
        self.root = Path(root).expanduser().resolve()
        self.read_only = read_only
        if not self.root.exists():
            raise StorageError(f"Local folder '{root}' does not exist")
        if not self.root.is_dir():
            raise StorageError(f"'{root}' is not a folder")

    # -- path safety -----------------------------------------------------------

    def resolve(self, key: str) -> Path:
        """Resolve *key* inside the workspace root, refusing escapes."""
        key = key.lstrip("/").replace("\\", "/")
        candidate = (self.root / key).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise NotFoundError(f"Invalid path '{key}'")
        return candidate

    def _entry(self, path: Path, key: str) -> BlobEntry:
        stat = path.stat()
        return BlobEntry(
            key=key,
            size=stat.st_size if path.is_file() else 0,
            last_modified=stat.st_mtime,
            etag=f"local-{int(stat.st_mtime_ns)}-{stat.st_size}",
            is_dir=path.is_dir(),
        )

    # -- reads -------------------------------------------------------------------

    def list_objects(self, prefix: str = "", delimiter: str = "/") -> tuple[list[BlobEntry], list[BlobEntry]]:
        base = self.resolve(prefix)
        if not base.exists():
            raise NotFoundError(f"'{prefix}' does not exist in this workspace")
        files: list[BlobEntry] = []
        dirs: list[BlobEntry] = []
        for child in sorted(base.iterdir(), key=lambda p: p.name.lower()):
            if child.name.startswith("."):
                continue
            rel = str(child.relative_to(self.root)).replace("\\", "/")
            dirs.append(
                BlobEntry(key=rel + ("/" if child.is_dir() else ""), size=0,
                          last_modified=child.stat().st_mtime, etag=None, is_dir=True)
            ) if child.is_dir() else files.append(self._entry(child, rel))
        return files, dirs

    def get(self, key: str) -> BlobEntry:
        path = self.resolve(key)
        if not path.exists():
            raise NotFoundError(f"'{key}' does not exist in this workspace")
        return self._entry(path, key.rstrip("/"))

    def iter_file(self, key: str, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
        path = self.resolve(key)
        if not path.is_file():
            raise NotFoundError(f"'{key}' does not exist in this workspace")
        with path.open("rb") as fh:
            while chunk := fh.read(chunk_size):
                yield chunk

    def open(self, key: str) -> BinaryIO:
        path = self.resolve(key)
        if not path.is_file():
            raise NotFoundError(f"'{key}' does not exist in this workspace")
        return path.open("rb")

    def download_to(self, key: str, dest_path: str) -> BlobEntry:
        entry = self.get(key)
        shutil.copyfile(self.resolve(key), dest_path)
        return entry

    def list_all(self, prefix: str = "", limit: int = 20000) -> list[BlobEntry]:
        base = self.resolve(prefix)
        if not base.exists():
            raise NotFoundError(f"'{prefix}' does not exist in this workspace")
        entries: list[BlobEntry] = []
        for path in sorted(base.rglob("*"), key=lambda p: str(p).lower()):
            if not path.is_file() or path.name.startswith("."):
                continue
            entries.append(
                self._entry(path, str(path.relative_to(self.root)).replace("\\", "/"))
            )
            if len(entries) >= limit:
                break
        return entries

    # -- writes ---------------------------------------------------------------

    def _ensure_writable(self) -> None:
        if self.read_only:
            raise ReadOnlyError("This workspace is marked as read-only")

    def write_file(self, key: str, data: bytes) -> BlobEntry:
        self._ensure_writable()
        path = self.resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return self._entry(path, key)

    def delete(self, key: str) -> None:
        self._ensure_writable()
        path = self.resolve(key)
        if not path.exists():
            raise NotFoundError(f"'{key}' does not exist in this workspace")
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

    def create_folder(self, key: str) -> None:
        self._ensure_writable()
        path = self.resolve(key.rstrip("/"))
        path.mkdir(parents=True, exist_ok=True)

    def rename(self, key: str, new_key: str) -> None:
        self._ensure_writable()
        src = self.resolve(key)
        dst = self.resolve(new_key)
        if not src.exists():
            raise NotFoundError(f"'{key}' does not exist in this workspace")
        if dst.exists():
            raise StorageError(f"'{new_key}' already exists")
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.rename(src, dst)

    def test_connection(self) -> dict:
        if not self.root.exists():
            raise NotFoundError(f"Folder '{self.root}' is gone")
        probe = self.root / ".blob-viewer-probe"
        if not self.read_only:
            try:
                probe.write_text(str(time.time()))
                probe.unlink()
            except OSError as exc:
                raise StorageError(f"Folder is not writable: {exc}") from exc
        return {"ok": True, "message": f"Folder '{self.root}' is accessible"}
