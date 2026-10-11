"""API tests using the Flask test client (no network needed)."""
from __future__ import annotations


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_workspace_crud_and_redaction(client, tmp_path):
    r = client.post("/api/workspaces", json={
        "name": "api-ws", "kind": "local", "local_path": str(tmp_path)})
    assert r.status_code == 201
    ws = r.get_json()["workspace"]
    wid = ws["id"]

    r = client.get("/api/workspaces")
    assert any(w["name"] == "api-ws" for w in r.get_json()["workspaces"])

    r = client.patch(f"/api/workspaces/{wid}", json={"description": "patched"})
    assert r.get_json()["workspace"]["description"] == "patched"

    assert client.delete(f"/api/workspaces/{wid}").status_code == 200
    assert client.get(f"/api/workspaces/{wid}").status_code == 404


def test_browse_open_raw_range(client, local_workspace):
    wid = local_workspace.id
    files = client.get(f"/api/workspaces/{wid}/objects").get_json()
    assert [d for d in files["dirs"]] == ["docs/"]
    assert files["files"][0]["key"] == "notes.txt"

    r = client.post(f"/api/workspaces/{wid}/open", json={"path": "docs/readme.md"})
    assert r.status_code == 200
    assert r.get_json()["category"] == "markdown"
    assert r.get_json()["downloaded"] is True

    r = client.get(f"/api/workspaces/{wid}/raw?path=docs%2Freadme.md")
    assert r.status_code == 200 and b"markdown" in r.data

    r = client.get(f"/api/workspaces/{wid}/raw?path=docs%2Freadme.md",
                   headers={"Range": "bytes=0-3"})
    assert r.status_code == 206 and r.data == b"# He"

    # second open must be served from cache (no re-download)
    r = client.post(f"/api/workspaces/{wid}/open", json={"path": "docs/readme.md"})
    assert r.get_json()["downloaded"] is False


def test_write_ops_local(client, local_workspace):
    wid = local_workspace.id
    assert client.put(f"/api/workspaces/{wid}/file",
                      json={"path": "new.txt", "content": "created"}).status_code == 200
    r = client.get(f"/api/workspaces/{wid}/raw?path=new.txt")
    assert r.data == b"created"

    assert client.post(f"/api/workspaces/{wid}/folder", json={"path": "afolder/"}).status_code == 200
    assert client.post(f"/api/workspaces/{wid}/rename",
                       json={"from": "new.txt", "to": "afolder/renamed.txt"}).status_code == 200
    assert client.delete(f"/api/workspaces/{wid}/file?path=afolder%2Frenamed.txt").status_code == 200


def test_check_versions_and_sync(client, local_workspace, tmp_path):
    wid = local_workspace.id
    client.post(f"/api/workspaces/{wid}/open", json={"path": "notes.txt"})
    versions = client.post(f"/api/workspaces/{wid}/check-versions",
                           json={"paths": ["notes.txt"]}).get_json()["versions"]
    assert versions["notes.txt"]["sync_available"] is False

    # modify upstream
    (tmp_path / "data" / "notes.txt").write_text("changed content upstream")
    versions = client.post(f"/api/workspaces/{wid}/check-versions",
                           json={"paths": ["notes.txt"]}).get_json()["versions"]
    assert versions["notes.txt"]["sync_available"] is True

    client.post(f"/api/workspaces/{wid}/sync", json={"path": "notes.txt"})
    r = client.get(f"/api/workspaces/{wid}/raw?path=notes.txt")
    assert b"upstream" in r.data


def test_search(client, local_workspace):
    res = client.get(f"/api/workspaces/{local_workspace.id}/search?q=readme").get_json()
    assert any("readme.md" in f["key"] for f in res["results"])


def test_cache_endpoints(client, local_workspace):
    client.post(f"/api/workspaces/{local_workspace.id}/open", json={"path": "notes.txt"})
    stats = client.get("/api/cache").get_json()
    assert stats["files"] >= 1
    r = client.post("/api/cache/clear", json={"workspace_id": local_workspace.id})
    assert r.get_json()["removed"] >= 1


def test_settings_roundtrip(client):
    r = client.put("/api/settings", json={"theme": "nord", "view_mode": "grid"})
    assert r.get_json()["settings"]["theme"] == "nord"
    r = client.put("/api/settings", json={"bogus": "x"})
    assert r.status_code == 400


def test_spa_served(client):
    r = client.get("/")
    assert r.status_code == 200 and b"Blob Viewer" in r.data
    r = client.get("/deep/route")
    assert r.status_code == 200


def test_locked_mode_requires_login(home, tmp_path):
    from blob_viewer.service import AppService
    from blob_viewer.api import create_app
    svc = AppService.create(home, locked=True)
    c = create_app(svc).test_client()

    # everything except health/session/login is gated
    assert c.get("/api/workspaces").status_code == 401
    assert c.get("/api/health").status_code == 200

    # first-run bootstrap via the API
    r = c.post("/api/auth/login", json={"username": "admin", "password": "password123"})
    assert r.status_code == 200 and r.get_json()["created"] is True
    assert "bv_session" in r.headers.get("Set-Cookie", "")

    assert c.get("/api/workspaces").status_code == 200
    session = c.get("/api/session").get_json()
    assert session["authenticated"] and session["username"] == "admin"

    # weak passwords rejected during bootstrap
    svc2 = AppService.create(home.__class__(home.root.parent / "home2"), locked=True)
    c2 = create_app(svc2).test_client()
    r = c2.post("/api/auth/login", json={"username": "a", "password": "short"})
    assert r.status_code == 400


def test_write_blocked_on_remote(home):
    """Remote (S3) workspaces reject every write operation with 403."""
    from blob_viewer.service import AppService
    from blob_viewer.api import create_app
    svc = AppService.create(home)
    ws = svc.workspaces.create({
        "name": "ro", "kind": "s3", "endpoint": "http://localhost:9000",
        "bucket": "blob-viewer-test", "path_style": True,
        "secrets": {"access_key": "rustfsadmin", "secret_key": "rustfsadmin"},
    })
    c = create_app(svc).test_client()
    base = f"/api/workspaces/{ws.id}"
    assert c.put(f"{base}/file", json={"path": "x.txt", "content": "y"}).status_code == 403
    assert c.delete(f"{base}/file?path=docs%2Freadme.md").status_code == 403
    assert c.post(f"{base}/folder", json={"path": "newfolder/"}).status_code == 403
    assert c.post(f"{base}/rename", json={"from": "a", "to": "b"}).status_code == 403
