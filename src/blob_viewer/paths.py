"""Filesystem layout for the Blob Viewer home directory.

Everything Blob Viewer persists lives in a single *home* folder:

    <home>/
      blob-viewer.db     SQLite database (workspaces, settings, cache index)
      secrets.key        Fernet key used to encrypt credentials at rest
      cache/             downloaded objects, organised per workspace

The home directory defaults to ``~/.blob-viewer`` and can be overridden with
the ``BLOB_VIEWER_HOME`` environment variable or the ``--home`` CLI flag.
For Docker deployments the image sets ``BLOB_VIEWER_HOME=/data``.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

HOME_ENV_VAR = "BLOB_VIEWER_HOME"
DEFAULT_HOME_NAME = ".blob-viewer"
DB_FILE = "blob-viewer.db"
KEY_FILE = "secrets.key"
CACHE_DIR = "cache"


class Home:
    """Resolved paths of a Blob Viewer home directory."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).expanduser().resolve()

    @classmethod
    def from_env(cls, override: str | os.PathLike[str] | None = None) -> "Home":
        """Resolve the home directory from *override*, env var or default."""
        candidate = override or os.environ.get(HOME_ENV_VAR) or Path.home() / DEFAULT_HOME_NAME
        return cls(Path(candidate))

    @property
    def db_path(self) -> Path:
        return self.root / DB_FILE

    @property
    def key_path(self) -> Path:
        return self.root / KEY_FILE

    @property
    def cache_dir(self) -> Path:
        return self.root / CACHE_DIR

    def ensure(self) -> None:
        """Create the directory tree if missing and lock down permissions."""
        self.root.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        _restrict(self.root)
        _restrict(self.cache_dir)

    def workspace_cache_dir(self, workspace_id: str) -> Path:
        path = self.cache_dir / _safe_dir_name(workspace_id)
        path.mkdir(parents=True, exist_ok=True)
        return path


def _restrict(path: Path) -> None:
    """Best-effort chmod 700 on POSIX (no-op on Windows filesystems)."""
    if os.name == "posix":
        try:
            path.chmod(stat.S_IRWXU)
        except OSError:
            pass


def _safe_dir_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name) or "ws"
