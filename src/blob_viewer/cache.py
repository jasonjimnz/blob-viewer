"""Local download cache.

Every file the user opens is stored once in ``<home>/cache/<workspace>/`` and
indexed in SQLite.  Subsequent opens are served from disk, even offline.  The
remote ETag (or a local mtime fingerprint) is recorded so Blob Viewer can tell
the user when a newer version exists upstream ("sync available") and fetch it
on demand.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .db import Database, now
from .paths import Home
from .storage import BlobEntry, NotFoundError, Storage


class CacheError(Exception):
    pass


@dataclass
class CachedFile:
    workspace_id: str
    key: str
    etag: str | None
    size: int | None
    last_modified: float | None
    local_path: str
    cached_at: float
    last_opened_at: float | None = None

    def to_api(self) -> dict:
        return {
            "workspace_id": self.workspace_id,
            "key": self.key,
            "etag": self.etag,
            "size": self.size,
            "last_modified": self.last_modified,
            "cached_at": self.cached_at,
            "last_opened_at": self.last_opened_at,
            "local_path": self.local_path,
        }


class CacheManager:
    def __init__(self, home: Home, db: Database) -> None:
        self.home = home
        self.db = db

    # -- paths ------------------------------------------------------------

    def local_path_for(self, workspace_id: str, key: str) -> Path:
        """Stable on-disk location for a workspace object."""
        ws_dir = self.home.workspace_cache_dir(workspace_id)
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        name = Path(key).name or "file"
        # keep the human name for readability, digest for uniqueness
        safe_name = "".join(ch if ch.isalnum() or ch in "._- " else "_" for ch in name)[:80]
        return ws_dir / f"{digest}-{safe_name}"

    # -- index ------------------------------------------------------------

    def get_entry(self, workspace_id: str, key: str) -> CachedFile | None:
        row = self.db.query_one(
            "SELECT * FROM cache_entries WHERE workspace_id = ? AND key = ?",
            (workspace_id, key),
        )
        return self._from_row(row) if row else None

    @staticmethod
    def _from_row(row: sqlite3.Row) -> CachedFile:
        return CachedFile(
            workspace_id=row["workspace_id"],
            key=row["key"],
            etag=row["etag"],
            size=row["size"],
            last_modified=row["last_modified"],
            local_path=row["local_path"],
            cached_at=row["cached_at"],
            last_opened_at=row["last_opened_at"],
        )

    def list_entries(self, workspace_id: str | None = None) -> list[CachedFile]:
        if workspace_id:
            rows = self.db.query_all(
                "SELECT * FROM cache_entries WHERE workspace_id = ? ORDER BY cached_at DESC",
                (workspace_id,),
            )
        else:
            rows = self.db.query_all("SELECT * FROM cache_entries ORDER BY cached_at DESC")
        return [self._from_row(r) for r in rows]

    def stats(self) -> dict:
        row = self.db.query_one(
            "SELECT COUNT(*) AS files, COALESCE(SUM(size), 0) AS bytes FROM cache_entries"
        )
        return {"files": row["files"], "bytes": row["bytes"]}

    # -- main operations ---------------------------------------------------

    def ensure_cached(self, workspace_id: str, key: str, storage: Storage) -> tuple[CachedFile, bool]:
        """Return a cached entry for *key*, downloading it if needed.

        Returns ``(entry, downloaded)``.  When a cached copy exists but its
        ETag no longer matches the remote one, the file is refreshed.
        """
        remote: BlobEntry = storage.get(key)
        cached = self.get_entry(workspace_id, key)
        if cached is not None and cached.etag and remote.etag and cached.etag == remote.etag:
            if Path(cached.local_path).exists():
                self.db.execute(
                    "UPDATE cache_entries SET last_opened_at = ? WHERE workspace_id = ? AND key = ?",
                    (now(), workspace_id, key),
                )
                return cached, False

        dest = self.local_path_for(workspace_id, key)
        entry = storage.download_to(key, str(dest))
        self.db.execute(
            "INSERT INTO cache_entries (workspace_id, key, etag, size, last_modified,"
            " local_path, cached_at, last_opened_at) VALUES (?,?,?,?,?,?,?,?)"
            " ON CONFLICT(workspace_id, key) DO UPDATE SET etag=excluded.etag,"
            " size=excluded.size, last_modified=excluded.last_modified,"
            " local_path=excluded.local_path, cached_at=excluded.cached_at,"
            " last_opened_at=excluded.last_opened_at",
            (
                workspace_id, key, entry.etag, entry.size, entry.last_modified,
                str(dest), now(), now(),
            ),
        )
        return self.get_entry(workspace_id, key), True  # type: ignore[return-value]

    def is_stale(self, workspace_id: str, key: str, storage: Storage) -> bool:
        """True when a newer version of the object exists upstream."""
        cached = self.get_entry(workspace_id, key)
        if cached is None:
            return False
        try:
            remote = storage.get(key)
        except NotFoundError:
            return False
        if not remote.etag or not cached.etag:
            return remote.last_modified is not None and cached.last_modified is not None and (
                remote.last_modified > cached.last_modified + 1
            )
        return remote.etag != cached.etag

    def check_versions(self, workspace_id: str, keys: list[str], storage: Storage) -> dict[str, dict]:
        """Batch version check: map each key to its sync status."""
        result: dict[str, dict] = {}
        for key in keys:
            cached = self.get_entry(workspace_id, key)
            try:
                remote = storage.get(key)
            except NotFoundError:
                result[key] = {"cached": bool(cached), "remote": False, "sync_available": False,
                               "remote_etag": None, "cached_etag": cached.etag if cached else None}
                continue
            sync_available = bool(
                cached
                and (
                    (remote.etag and cached.etag and remote.etag != cached.etag)
                    or (not remote.etag and remote.last_modified and cached.last_modified
                        and remote.last_modified > cached.last_modified + 1)
                )
            )
            result[key] = {
                "cached": bool(cached and Path(cached.local_path).exists()),
                "remote": True,
                "sync_available": sync_available,
                "remote_etag": remote.etag,
                "remote_last_modified": remote.last_modified,
                "cached_etag": cached.etag if cached else None,
                "cached_at": cached.cached_at if cached else None,
            }
        return result

    def remove_entry(self, workspace_id: str, key: str) -> None:
        cached = self.get_entry(workspace_id, key)
        if cached:
            Path(cached.local_path).unlink(missing_ok=True)
            self.db.execute(
                "DELETE FROM cache_entries WHERE workspace_id = ? AND key = ?",
                (workspace_id, key),
            )

    def clear(self, workspace_id: str | None = None) -> int:
        """Delete cached files (and index rows).  Returns removed file count."""
        entries = self.list_entries(workspace_id)
        count = 0
        for entry in entries:
            try:
                Path(entry.local_path).unlink(missing_ok=True)
                count += 1
            except OSError:
                pass
        if workspace_id:
            self.db.execute(
                "DELETE FROM cache_entries WHERE workspace_id = ?", (workspace_id,)
            )
        else:
            self.db.execute("DELETE FROM cache_entries")
        # remove empty workspace dirs
        for ws_dir in self.home.cache_dir.iterdir():
            if ws_dir.is_dir() and not any(ws_dir.iterdir()):
                ws_dir.rmdir()
        return count
