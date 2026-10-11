"""End-to-end tests against a real S3-compatible server.

Run with:  pytest -m e2e
Requires:  an S3 endpoint configured via the BLOB_VIEWER_E2E_S3_* environment
           variables (see tests/conftest.py).  Skipped when not configured.
"""
from __future__ import annotations

import boto3
import pytest
from botocore.client import Config

from tests.conftest import RUSTFS_ACCESS, RUSTFS_BUCKET, RUSTFS_ENDPOINT, RUSTFS_SECRET, needs_s3

pytestmark = [pytest.mark.e2e, needs_s3]


def s3():
    return boto3.client(
        "s3", endpoint_url=RUSTFS_ENDPOINT,
        aws_access_key_id=RUSTFS_ACCESS, aws_secret_access_key=RUSTFS_SECRET,
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


@pytest.fixture(scope="module", autouse=True)
def fixtures():
    c = s3()
    buckets = [b["Name"] for b in c.list_buckets()["Buckets"]]
    if RUSTFS_BUCKET not in buckets:
        c.create_bucket(Bucket=RUSTFS_BUCKET)
    c.put_object(Bucket=RUSTFS_BUCKET, Key="e2e/hello.md", Body="# E2E Hello\n\nfrom **RustFS**")
    c.put_object(Bucket=RUSTFS_BUCKET, Key="e2e/app.py", Body='print("e2e")\n')
    yield


def test_list_and_open(client_fixture, rustfs_ws):
    c, wid = client_fixture
    c.post(f"/api/workspaces/{wid}/evict", json={"path": "e2e/hello.md"})
    r = c.get(f"/api/workspaces/{wid}/objects?prefix=e2e/")
    keys = [f["key"] for f in r.get_json()["files"]]
    assert "e2e/hello.md" in keys and "e2e/app.py" in keys

    r = c.post(f"/api/workspaces/{wid}/open", json={"path": "e2e/hello.md"})
    body = r.get_json()
    assert body["category"] == "markdown"
    assert body["downloaded"] is True

    r = c.get(f"/api/workspaces/{wid}/raw?path=e2e%2Fhello.md")
    assert b"RustFS" in r.data


def test_download_once(client_fixture, rustfs_ws):
    c, wid = client_fixture
    c.post(f"/api/workspaces/{wid}/evict", json={"path": "e2e/hello.md"})
    assert c.post(f"/api/workspaces/{wid}/open", json={"path": "e2e/hello.md"}).get_json()["downloaded"]
    assert not c.post(f"/api/workspaces/{wid}/open", json={"path": "e2e/hello.md"}).get_json()["downloaded"]


def test_remote_change_detected_and_synced(client_fixture, rustfs_ws):
    c, wid = client_fixture
    c.post(f"/api/workspaces/{wid}/open", json={"path": "e2e/hello.md"})

    s3().put_object(Bucket=RUSTFS_BUCKET, Key="e2e/hello.md",
                    Body="# E2E Hello\n\nUPDATED upstream")
    versions = c.post(f"/api/workspaces/{wid}/check-versions",
                      json={"paths": ["e2e/hello.md"]}).get_json()["versions"]
    assert versions["e2e/hello.md"]["sync_available"] is True

    c.post(f"/api/workspaces/{wid}/sync", json={"path": "e2e/hello.md"})
    assert b"UPDATED" in c.get(f"/api/workspaces/{wid}/raw?path=e2e%2Fhello.md").data
    versions = c.post(f"/api/workspaces/{wid}/check-versions",
                      json={"paths": ["e2e/hello.md"]}).get_json()["versions"]
    assert versions["e2e/hello.md"]["sync_available"] is False


def test_search_across_bucket(client_fixture, rustfs_ws):
    c, wid = client_fixture
    res = c.get(f"/api/workspaces/{wid}/search?q=app.py").get_json()
    assert any(f["key"] == "e2e/app.py" for f in res["results"])
