"""Workspace management: registration, credentials and redaction.

A *workspace* is a named source of files.  Two kinds exist:

``s3``
    Any S3-compatible bucket (AWS S3, MinIO, Backblaze B2, Cloudflare R2,
    DigitalOcean Spaces, Wasabi, ...).  Always **read-only** inside Blob
    Viewer — remote files are downloaded to the cache for viewing but never
    modified in place.

``local``
    A folder on the local machine.  Private by definition (no network) and
    writable, so files can be created, edited and deleted.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any

from .db import Database, new_id, now
from .secrets import SecretStore

S3_SECRET_FIELDS = ("access_key", "secret_key")
SECRET_FIELDS = S3_SECRET_FIELDS  # future kinds may add more

REDACTED_SENTINEL = "__REDACTED__"


class WorkspaceError(Exception):
    pass


class WorkspaceNotFound(WorkspaceError):
    pass


@dataclass
class Workspace:
    id: str
    name: str
    kind: str  # 's3' | 'local'
    endpoint: str | None = None
    bucket: str | None = None
    region: str | None = None
    prefix: str | None = None
    path_style: bool = False
    local_path: str | None = None
    read_only: bool = False
    description: str | None = None
    color: str | None = None
    created_at: float = 0.0
    last_used_at: float | None = None
    # populated separately (never serialised to disk in clear text):
    secrets: dict[str, str | None] = field(default_factory=dict)

    @property
    def is_remote(self) -> bool:
        return self.kind == "s3"

    @property
    def writable(self) -> bool:
        return self.kind == "local" and not self.read_only

    def to_api(self, redacted: bool = True) -> dict[str, Any]:
        """Serialise for the API.  Secrets are always redacted."""
        data = {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "endpoint": self.endpoint,
            "bucket": self.bucket,
            "region": self.region,
            "prefix": self.prefix,
            "path_style": self.path_style,
            "local_path": self.local_path,
            "read_only": self.read_only or self.is_remote,
            "writable": self.writable,
            "description": self.description,
            "color": self.color,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "has_secrets": {k: bool(self.secrets.get(k)) for k in SECRET_FIELDS},
        }
        if redacted:
            data["secrets"] = {
                k: SecretStore.redact(v) if v else None for k, v in self.secrets.items()
            }
        return data


class WorkspaceStore:
    """CRUD operations for workspaces and their encrypted secrets."""

    def __init__(self, db: Database, secret_store: SecretStore) -> None:
        self.db = db
        self.secrets = secret_store

    # -- reads -------------------------------------------------------------

    def list(self) -> list[Workspace]:
        rows = self.db.query_all("SELECT * FROM workspaces ORDER BY name COLLATE NOCASE")
        return [self._hydrate(row) for row in rows]

    def get(self, workspace_id: str) -> Workspace:
        row = self.db.query_one("SELECT * FROM workspaces WHERE id = ?", (workspace_id,))
        if row is None:
            raise WorkspaceNotFound(f"Workspace '{workspace_id}' does not exist")
        return self._hydrate(row)

    def get_by_name(self, name: str) -> Workspace | None:
        row = self.db.query_one(
            "SELECT * FROM workspaces WHERE name = ? COLLATE NOCASE", (name,)
        )
        return self._hydrate(row) if row else None

    def _hydrate(self, row: sqlite3.Row) -> Workspace:
        ws = Workspace(
            id=row["id"],
            name=row["name"],
            kind=row["kind"],
            endpoint=row["endpoint"],
            bucket=row["bucket"],
            region=row["region"],
            prefix=row["prefix"],
            path_style=bool(row["path_style"]),
            local_path=row["local_path"],
            read_only=bool(row["read_only"]),
            description=row["description"],
            color=row["color"],
            created_at=row["created_at"],
            last_used_at=row["last_used_at"],
        )
        for field_name in SECRET_FIELDS:
            row_secret = self.db.query_one(
                "SELECT ciphertext FROM workspace_secrets WHERE workspace_id = ? AND field = ?",
                (ws.id, field_name),
            )
            if row_secret:
                ws.secrets[field_name] = self.secrets.decrypt(row_secret["ciphertext"])
            else:
                ws.secrets[field_name] = None
        return ws

    # -- writes ------------------------------------------------------------

    def create(self, data: dict[str, Any]) -> Workspace:
        kind = data.get("kind")
        if kind not in ("s3", "local"):
            raise WorkspaceError("Workspace kind must be 's3' or 'local'")
        name = (data.get("name") or "").strip()
        if not name:
            raise WorkspaceError("Workspace name is required")
        if self.get_by_name(name):
            raise WorkspaceError(f"A workspace named '{name}' already exists")

        ws = Workspace(
            id=new_id(),
            name=name,
            kind=kind,
            endpoint=(data.get("endpoint") or None),
            bucket=(data.get("bucket") or None),
            region=(data.get("region") or None),
            prefix=(data.get("prefix") or None),
            path_style=bool(data.get("path_style", kind == "s3")),
            local_path=(data.get("local_path") or None),
            read_only=bool(data.get("read_only", kind == "s3")),
            description=(data.get("description") or None),
            color=(data.get("color") or None),
            created_at=now(),
        )
        self._validate(ws)
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO workspaces (id, name, kind, endpoint, bucket, region, prefix,"
                " path_style, local_path, read_only, description, color, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    ws.id, ws.name, ws.kind, ws.endpoint, ws.bucket, ws.region, ws.prefix,
                    int(ws.path_style), ws.local_path, int(ws.read_only), ws.description,
                    ws.color, ws.created_at,
                ),
            )
            self._write_secrets(conn, ws, data.get("secrets") or {})
        return self.get(ws.id)

    def update(self, workspace_id: str, data: dict[str, Any]) -> Workspace:
        current = self.get(workspace_id)
        name = data.get("name", current.name)
        if name != current.name and self.get_by_name(name):
            raise WorkspaceError(f"A workspace named '{name}' already exists")

        merged = {
            "name": name,
            "endpoint": data.get("endpoint", current.endpoint) or None,
            "bucket": data.get("bucket", current.bucket) or None,
            "region": data.get("region", current.region) or None,
            "prefix": data.get("prefix", current.prefix) or None,
            "path_style": data.get("path_style", current.path_style),
            "local_path": data.get("local_path", current.local_path) or None,
            "read_only": data.get("read_only", current.read_only),
            "description": data.get("description", current.description) or None,
            "color": data.get("color", current.color) or None,
        }
        self._validate_fields(
            kind=current.kind, name=merged["name"],
            endpoint=merged["endpoint"], bucket=merged["bucket"],
            local_path=merged["local_path"],
        )
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE workspaces SET name=?, endpoint=?, bucket=?, region=?, prefix=?,"
                " path_style=?, local_path=?, read_only=?, description=?, color=? WHERE id=?",
                (
                    merged["name"], merged["endpoint"], merged["bucket"], merged["region"],
                    merged["prefix"], int(bool(merged["path_style"])), merged["local_path"],
                    int(bool(merged["read_only"])), merged["description"], merged["color"],
                    workspace_id,
                ),
            )
            # Update secrets only for fields explicitly provided.  The redacted
            # sentinel means "keep what is stored".
            incoming = data.get("secrets") or {}
            updatable = {
                k: v for k, v in incoming.items()
                if k in SECRET_FIELDS and v != REDACTED_SENTINEL
            }
            current.secrets.update(updatable)
            self._write_secrets(conn, current, updatable, overwrite=False)
            current.secrets.update(
                {k: v for k, v in incoming.items() if k in SECRET_FIELDS}
            )
        return self.get(workspace_id)

    def delete(self, workspace_id: str) -> None:
        self.get(workspace_id)  # raises if missing
        with self.db.connect() as conn:
            conn.execute("DELETE FROM workspaces WHERE id = ?", (workspace_id,))
            conn.execute(
                "DELETE FROM workspace_secrets WHERE workspace_id = ?", (workspace_id,)
            )
            conn.execute(
                "DELETE FROM cache_entries WHERE workspace_id = ?", (workspace_id,)
            )

    def touch(self, workspace_id: str) -> None:
        self.db.execute(
            "UPDATE workspaces SET last_used_at = ? WHERE id = ?", (now(), workspace_id)
        )

    # -- internals ----------------------------------------------------------

    def _write_secrets(
        self,
        conn: sqlite3.Connection,
        ws: Workspace,
        values: dict[str, str | None],
        overwrite: bool = True,
    ) -> None:
        for field_name, value in values.items():
            if field_name not in SECRET_FIELDS:
                continue
            if value is None and not overwrite:
                continue
            if value is None:
                conn.execute(
                    "DELETE FROM workspace_secrets WHERE workspace_id = ? AND field = ?",
                    (ws.id, field_name),
                )
                continue
            ciphertext = self.secrets.encrypt(value)
            conn.execute(
                "INSERT INTO workspace_secrets (workspace_id, field, ciphertext) VALUES (?,?,?)"
                " ON CONFLICT(workspace_id, field) DO UPDATE SET ciphertext = excluded.ciphertext",
                (ws.id, field_name, ciphertext),
            )

    def _validate(self, ws: Workspace) -> None:
        self._validate_fields(
            kind=ws.kind, name=ws.name, endpoint=ws.endpoint,
            bucket=ws.bucket, local_path=ws.local_path,
        )

    @staticmethod
    def _validate_fields(
        *, kind: str, name: str, endpoint: str | None,
        bucket: str | None, local_path: str | None,
    ) -> None:
        if not name:
            raise WorkspaceError("Workspace name is required")
        if kind == "s3":
            if not endpoint:
                raise WorkspaceError("S3 workspaces require an endpoint URL")
            if not bucket:
                raise WorkspaceError("S3 workspaces require a bucket name")
        elif kind == "local":
            if not local_path:
                raise WorkspaceError("Local workspaces require a folder path")
