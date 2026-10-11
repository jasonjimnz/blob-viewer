"""Shared fixtures for Blob Viewer tests."""
from __future__ import annotations

import os
import pathlib
import sys

import pytest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from blob_viewer.api import create_app  # noqa: E402
from blob_viewer.paths import Home  # noqa: E402
from blob_viewer.service import AppService  # noqa: E402

# Credentials for the optional real-S3 e2e tests.  Never hard-coded: set them
# in your environment when running the e2e suite against your own instance.
#   BLOB_VIEWER_E2E_S3_ENDPOINT   e.g. http://localhost:9000
#   BLOB_VIEWER_E2E_S3_ACCESS
#   BLOB_VIEWER_E2E_S3_SECRET
#   BLOB_VIEWER_E2E_S3_BUCKET
RUSTFS_ENDPOINT = os.environ.get("BLOB_VIEWER_E2E_S3_ENDPOINT", "http://localhost:9000")
RUSTFS_ACCESS = os.environ.get("BLOB_VIEWER_E2E_S3_ACCESS", "")
RUSTFS_SECRET = os.environ.get("BLOB_VIEWER_E2E_S3_SECRET", "")
RUSTFS_BUCKET = os.environ.get("BLOB_VIEWER_E2E_S3_BUCKET", "blob-viewer-test")

E2E_S3_AVAILABLE = bool(RUSTFS_ACCESS and RUSTFS_SECRET)

needs_s3 = pytest.mark.skipif(
    not E2E_S3_AVAILABLE,
    reason="set BLOB_VIEWER_E2E_S3_ENDPOINT/ACCESS/SECRET to run real-S3 e2e tests",
)


@pytest.fixture()
def home(tmp_path):
    h = Home(tmp_path / "home")
    h.ensure()
    return h


@pytest.fixture()
def service(home):
    return AppService.create(home)


@pytest.fixture()
def client(service):
    return create_app(service).test_client()


@pytest.fixture()
def local_workspace(service, tmp_path):
    data = tmp_path / "data"
    (data / "docs").mkdir(parents=True)
    (data / "docs" / "readme.md").write_text("# Hello\n\nSome **markdown** text.")
    (data / "docs" / "script.py").write_text('def main():\n    print("hi")\n')
    (data / "notes.txt").write_text("plain text note")
    ws = service.workspaces.create(
        {"name": "local-test", "kind": "local", "local_path": str(data)}
    )
    return ws


@pytest.fixture(scope="session")
def rustfs_workspace(service_session):
    """Requires RustFS (S3-compatible) running on localhost:9000."""
    ws = service_session.workspaces.create(
        {
            "name": "rustfs-e2e",
            "kind": "s3",
            "endpoint": RUSTFS_ENDPOINT,
            "bucket": RUSTFS_BUCKET,
            "path_style": True,
            "secrets": {"access_key": RUSTFS_ACCESS, "secret_key": RUSTFS_SECRET},
        }
    )
    return ws


@pytest.fixture(scope="session")
def service_session(tmp_path_factory):
    home = Home(tmp_path_factory.mktemp("bv-session") / "home")
    return AppService.create(home)


@pytest.fixture(scope="session")
def rustfs_ws(service_session):
    """Requires a real S3 endpoint via BLOB_VIEWER_E2E_S3_* environment variables."""
    existing = [w for w in service_session.workspaces.list() if w.name == "rustfs-e2e"]
    if existing:
        return existing[0]
    return service_session.workspaces.create(
        {
            "name": "rustfs-e2e",
            "kind": "s3",
            "endpoint": RUSTFS_ENDPOINT,
            "bucket": RUSTFS_BUCKET,
            "path_style": True,
            "secrets": {"access_key": RUSTFS_ACCESS, "secret_key": RUSTFS_SECRET},
        }
    )


@pytest.fixture(scope="session")
def client_fixture(service_session, rustfs_ws):
    """(test_client, workspace_id) bound to the session service."""
    app = create_app(service_session)
    return app.test_client(), rustfs_ws.id
