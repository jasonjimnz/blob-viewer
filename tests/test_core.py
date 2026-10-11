"""Unit tests for the core layer: secrets, workspaces, cache, auth, preview."""
from __future__ import annotations

from blob_viewer.auth import AuthError, AuthService
from blob_viewer.cache import CacheManager
from blob_viewer.preview import category_for, hljs_language, mime_for
from blob_viewer.secrets import SecretStore
from blob_viewer.storage import LocalStorage, StorageError
from blob_viewer.workspaces import WorkspaceError, WorkspaceStore


# -- secrets ------------------------------------------------------------------

def test_secret_roundtrip(tmp_path):
    store = SecretStore(tmp_path / "secrets.key")
    blob = store.encrypt("super-secret-value")
    assert b"super-secret" not in blob
    assert store.decrypt(blob) == "super-secret-value"


def test_redact():
    assert SecretStore.redact("abcdefgh") == "••••efgh"
    assert SecretStore.redact("abc") == "••••"
    assert SecretStore.redact(None) is None


def test_key_reuse(tmp_path):
    store = SecretStore(tmp_path / "secrets.key")
    blob = store.encrypt("value")
    # second instance reads the same key file
    assert SecretStore(tmp_path / "secrets.key").decrypt(blob) == "value"


# -- workspaces ----------------------------------------------------------------

def test_create_and_redact(service):
    ws = service.workspaces.create(
        {"name": "w1", "kind": "s3", "endpoint": "http://x", "bucket": "b",
         "secrets": {"access_key": "AKIA1234", "secret_key": "shhh1234"}}
    )
    api = ws.to_api()
    assert api["secrets"]["secret_key"] == "••••1234"
    assert api["has_secrets"]["secret_key"] is True
    assert api["read_only"] is True and api["writable"] is False


def test_duplicate_name_rejected(service):
    service.workspaces.create({"name": "dup", "kind": "local", "local_path": "/tmp"})
    import pytest
    with pytest.raises(WorkspaceError):
        service.workspaces.create({"name": "DUP", "kind": "local", "local_path": "/x"})


def test_validation(service):
    import pytest
    with pytest.raises(WorkspaceError):
        service.workspaces.create({"name": "no-endpoint", "kind": "s3", "bucket": "b"})
    with pytest.raises(WorkspaceError):
        service.workspaces.create({"name": "no-path", "kind": "local"})


def test_update_keeps_secrets(service, tmp_path):
    ws = service.workspaces.create(
        {"name": "keep", "kind": "s3", "endpoint": "http://x", "bucket": "b",
         "secrets": {"access_key": "AKIA", "secret_key": "SECRET1"}}
    )
    # PATCH without touching secrets: sentinel preserves stored values
    updated = service.workspaces.update(ws.id, {"bucket": "b2", "secrets": {"secret_key": "__REDACTED__"}})
    assert updated.secrets["secret_key"] == "SECRET1"
    assert updated.bucket == "b2"


def test_delete_cascades(service, tmp_path):
    ws = service.workspaces.create({"name": "gone", "kind": "local", "local_path": str(tmp_path)})
    service.workspaces.delete(ws.id)
    assert all(w.id != ws.id for w in service.workspaces.list())


# -- local storage ----------------------------------------------------------------

def test_local_storage_listing_and_writes(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.txt").write_text("hello")
    st = LocalStorage(str(tmp_path))
    files, dirs = st.list_objects()
    assert dirs[0].key == "sub/"
    assert files == []
    st.write_file("sub/b.txt", "data".encode())
    assert st.get("sub/b.txt").size == 4
    st.delete("sub/b.txt")


def test_local_path_traversal_blocked(tmp_path):
    st = LocalStorage(str(tmp_path))
    import pytest
    from blob_viewer.storage import NotFoundError
    with pytest.raises(NotFoundError):
        st.resolve("../outside.txt")


def test_read_only_local(tmp_path):
    import pytest
    from blob_viewer.storage import ReadOnlyError
    st = LocalStorage(str(tmp_path), read_only=True)
    with pytest.raises(ReadOnlyError):
        st.write_file("x.txt", b"data")


# -- cache ---------------------------------------------------------------------

def test_cache_download_once_and_staleness(service, tmp_path):
    data = tmp_path / "src"
    data.mkdir()
    f = data / "file.txt"
    f.write_text("v1")
    st = LocalStorage(str(data))
    cache = CacheManager(service.home, service.db)

    entry, downloaded = cache.ensure_cached("ws", "file.txt", st)
    assert downloaded and f.read_bytes() == b"v1"
    _, downloaded2 = cache.ensure_cached("ws", "file.txt", st)
    assert not downloaded2  # served from cache

    f.write_text("v2-with-longer-content")
    assert cache.is_stale("ws", "file.txt", st)
    entry3, downloaded3 = cache.ensure_cached("ws", "file.txt", st)
    assert downloaded3  # refreshed because content changed
    assert b"v2" in open(entry3.local_path, "rb").read()


def test_cache_clear(service, tmp_path):
    data = tmp_path / "src"
    data.mkdir()
    (data / "a.txt").write_text("content")
    st = LocalStorage(str(data))
    cache = CacheManager(service.home, service.db)
    cache.ensure_cached("ws1", "a.txt", st)
    assert cache.stats()["files"] == 1
    assert cache.clear() == 1
    assert cache.stats()["files"] == 0


# -- auth ------------------------------------------------------------------------

def test_auth_lifecycle(service):
    auth = AuthService(service.db)
    assert not auth.has_user()
    auth.create_user("admin", "longpassword1")
    assert auth.has_user()
    token = auth.login("admin", "longpassword1")
    assert auth.validate_session(token) == "admin"
    auth.logout(token)
    assert auth.validate_session(token) is None
    assert not auth.verify_credentials("admin", "wrongpass1")


def test_auth_requires_strong_password(service):
    import pytest
    with pytest.raises(AuthError):
        AuthService(service.db).create_user("admin", "short")


# -- preview -----------------------------------------------------------------------

def test_categories():
    assert category_for("readme.md") == "markdown"
    assert category_for("doc.PDF") == "pdf"
    assert category_for("main.py") == "code"
    assert category_for("photo.png") == "image"
    assert category_for("song.mp3") == "audio"
    assert category_for("clip.mp4") == "video"
    assert category_for("data.csv") == "csv"
    assert category_for("Dockerfile") == "code"
    assert category_for("app.exe") == "binary"
    assert category_for("notes.txt") == "text"


def test_mime():
    assert mime_for("doc.pdf") == "application/pdf"
    assert mime_for("img.png") == "image/png"
    assert mime_for("unknown.xyz") == "application/octet-stream"
    assert mime_for("file.md").startswith("text/")


def test_hljs():
    assert hljs_language("a.py") == "python"
    assert hljs_language("a.unknown") is None


def test_storage_error_on_missing_root(tmp_path):
    import pytest
    with pytest.raises(StorageError):
        LocalStorage(str(tmp_path / "does-not-exist"))
