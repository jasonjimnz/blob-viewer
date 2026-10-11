"""SQLite persistence layer.

Blob Viewer stores all structured state in a single SQLite database inside the
application home.  Access goes through :class:`Database`, a thin wrapper that
opens short-lived connections with WAL mode enabled and applies the schema on
first use.
"""

from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from pathlib import Path

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS workspaces (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    kind         TEXT NOT NULL CHECK (kind IN ('s3', 'local')),
    endpoint     TEXT,
    bucket       TEXT,
    region       TEXT,
    prefix       TEXT,
    path_style   INTEGER NOT NULL DEFAULT 0,
    local_path   TEXT,
    read_only    INTEGER NOT NULL DEFAULT 0,
    description  TEXT,
    color        TEXT,
    created_at   REAL NOT NULL,
    last_used_at REAL
);

CREATE TABLE IF NOT EXISTS workspace_secrets (
    workspace_id TEXT NOT NULL,
    field        TEXT NOT NULL,
    ciphertext   BLOB NOT NULL,
    PRIMARY KEY (workspace_id, field)
);

CREATE TABLE IF NOT EXISTS cache_entries (
    workspace_id TEXT NOT NULL,
    key          TEXT NOT NULL,
    etag         TEXT,
    size         INTEGER,
    last_modified REAL,
    local_path   TEXT NOT NULL,
    cached_at    REAL NOT NULL,
    last_opened_at REAL,
    PRIMARY KEY (workspace_id, key)
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    token      TEXT PRIMARY KEY,
    username   TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
"""


def now() -> float:
    return time.time()


def new_id() -> str:
    return uuid.uuid4().hex


class Database:
    """Thread-safe accessor for the SQLite database file."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._initialised = False

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def initialise(self) -> None:
        """Create tables if needed (idempotent)."""
        if self._initialised:
            return
        with self._lock, self.connect() as conn:
            conn.executescript(_SCHEMA)
            conn.execute(
                "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
        self._initialised = True

    # -- generic helpers ---------------------------------------------------

    def execute(self, sql: str, params: tuple | list = ()) -> None:
        with self._lock, self.connect() as conn:
            conn.execute(sql, params)

    def query_one(self, sql: str, params: tuple | list = ()) -> sqlite3.Row | None:
        with self._lock, self.connect() as conn:
            return conn.execute(sql, params).fetchone()

    def query_all(self, sql: str, params: tuple | list = ()) -> list[sqlite3.Row]:
        with self._lock, self.connect() as conn:
            return conn.execute(sql, params).fetchall()

    # -- settings ----------------------------------------------------------

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.query_one("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
