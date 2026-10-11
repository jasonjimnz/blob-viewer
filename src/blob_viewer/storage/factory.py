"""Storage factory: build the right backend for a workspace."""

from __future__ import annotations

from ..workspaces import Workspace
from . import LocalStorage, S3Storage, Storage


def storage_for(workspace: Workspace) -> Storage:
    """Instantiate the backend matching *workspace* (validates credentials)."""
    if workspace.kind == "s3":
        return S3Storage(
            endpoint=workspace.endpoint or "",
            bucket=workspace.bucket or "",
            access_key=workspace.secrets.get("access_key"),
            secret_key=workspace.secrets.get("secret_key"),
            region=workspace.region,
            prefix=workspace.prefix or "",
            path_style=workspace.path_style,
        )
    if workspace.kind == "local":
        return LocalStorage(
            root=workspace.local_path or "",
            read_only=workspace.read_only,
        )
    raise ValueError(f"Unknown workspace kind '{workspace.kind}'")
