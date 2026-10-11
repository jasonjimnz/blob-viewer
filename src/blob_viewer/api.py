"""HTTP API for Blob Viewer (Flask).

JSON REST API under ``/api/`` plus the single-page UI at ``/``.  When the app
runs in locked mode every API call requires a valid session cookie, obtained
from ``POST /api/auth/login``.
"""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path

from flask import Flask, Response, g, jsonify, render_template, request, send_file
from werkzeug.exceptions import BadRequest

# Ensure JS-module and friends are served with strict-correct MIME types.
# On Windows, mimetypes may resolve .mjs to text/plain (or miss it entirely),
# which makes browsers refuse dynamic module imports (pdf.js viewer etc.).
for _ext, _mime in (
    (".mjs", "text/javascript"),
    (".js", "text/javascript"),
    (".wasm", "application/wasm"),
    (".svg", "image/svg+xml"),
):
    mimetypes.add_type(_mime, _ext)


from . import __version__
from .auth import AuthError
from .cache import CacheError
from .preview import category_for, hljs_language, mime_for
from .service import AppService
from .storage import NotFoundError, ReadOnlyError, StorageError, factory
from .workspaces import REDACTED_SENTINEL, WorkspaceError, WorkspaceNotFound

SESSION_COOKIE = "bv_session"


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def create_app(service: AppService) -> Flask:
    app = Flask(
        "blob-viewer",
        static_folder=Path(__file__).parent / "static",
        static_url_path="/static",
        template_folder=Path(__file__).parent / "templates",
    )
    app.config["JSON_SORT_KEYS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # 512 MB uploads
    app.json.ensure_ascii = False

    # -- auth gate ------------------------------------------------------------

    @app.before_request
    def _auth_gate() -> Response | None:
        if not request.path.startswith("/api/"):
            return None
        if request.path in ("/api/health",) or request.path == "/api/session":
            return None
        if request.path == "/api/auth/login" and request.method == "POST":
            return None
        if not service.locked:
            return None
        token = request.cookies.get(SESSION_COOKIE)
        username = service.auth.validate_session(token)
        if username is None:
            return jsonify(error="Authentication required", code="auth_required"), 401
        g.username = username
        return None

    # -- error handling ---------------------------------------------------------

    def _bad_request(exc: Exception) -> tuple[Response, int]:
        return jsonify(error=str(exc) or exc.__class__.__name__), 400

    @app.errorhandler(ApiError)
    def _api_error(exc: ApiError) -> tuple[Response, int]:
        return jsonify(error=exc.message), exc.status

    @app.errorhandler(WorkspaceNotFound)
    def _ws_not_found(exc: WorkspaceNotFound) -> tuple[Response, int]:
        return jsonify(error=str(exc)), 404

    @app.errorhandler(NotFoundError)
    def _not_found(exc: NotFoundError) -> tuple[Response, int]:
        return jsonify(error=str(exc)), 404

    @app.errorhandler(ReadOnlyError)
    def _read_only(exc: ReadOnlyError) -> tuple[Response, int]:
        return jsonify(error=str(exc), code="read_only"), 403

    for exc_class in (StorageError, WorkspaceError, CacheError, AuthError, BadRequest, ValueError, KeyError):
        app.errorhandler(exc_class)(_bad_request)

    @app.errorhandler(500)
    def _server_error(exc: Exception) -> tuple[Response, int]:
        return jsonify(error="Internal server error", detail=str(exc)), 500

    # -- helpers ----------------------------------------------------------------

    def require_workspace(workspace_id: str):
        return service.workspaces.get(workspace_id)

    def backend_for(workspace):
        return factory.storage_for(workspace)

    # -- session / auth -----------------------------------------------------------

    @app.get("/api/health")
    def health():
        return jsonify(status="ok", version=__version__, locked=service.locked)

    @app.get("/api/session")
    def session_info():
        token = request.cookies.get(SESSION_COOKIE)
        username = service.auth.validate_session(token) if service.locked else None
        return jsonify(
            version=__version__,
            locked=service.locked,
            authenticated=(not service.locked) or username is not None,
            username=username,
            needs_setup=service.locked and not service.auth.has_user(),
        )

    @app.post("/api/auth/login")
    def login():
        if not service.locked:
            return jsonify(ok=True, message="Authentication is disabled (not locked)")
        body = json_body()
        if service.auth.has_user() is False:
            # first run in locked mode: bootstrap the master admin
            username = (body.get("username") or "").strip()
            password = body.get("password") or ""
            confirm = body.get("confirm_password") or ""
            if confirm and confirm != password:
                raise ApiError("Passwords do not match", 400)
            try:
                service.auth.create_user(username, password)
            except AuthError as exc:
                raise ApiError(str(exc), 400) from exc
            token = service.auth.login(username, password)
            resp = jsonify(ok=True, created=True)
            _set_session_cookie(resp, token)
            return resp
        token = service.auth.login(body.get("username") or "", body.get("password") or "")
        resp = jsonify(ok=True)
        _set_session_cookie(resp, token)
        return resp

    @app.post("/api/auth/logout")
    def logout():
        service.auth.logout(request.cookies.get(SESSION_COOKIE))
        resp = jsonify(ok=True)
        resp.delete_cookie(SESSION_COOKIE)
        return resp

    # -- workspaces ---------------------------------------------------------------

    @app.get("/api/workspaces")
    def list_workspaces():
        return jsonify(workspaces=[ws.to_api() for ws in service.workspaces.list()])

    @app.post("/api/workspaces")
    def create_workspace():
        ws = service.workspaces.create(json_body())
        return jsonify(workspace=ws.to_api()), 201

    @app.get("/api/workspaces/<workspace_id>")
    def get_workspace(workspace_id: str):
        return jsonify(workspace=require_workspace(workspace_id).to_api())

    @app.patch("/api/workspaces/<workspace_id>")
    def update_workspace(workspace_id: str):
        ws = service.workspaces.update(workspace_id, json_body())
        return jsonify(workspace=ws.to_api())

    @app.delete("/api/workspaces/<workspace_id>")
    def delete_workspace(workspace_id: str):
        require_workspace(workspace_id)
        service.workspaces.delete(workspace_id)
        return jsonify(ok=True)

    @app.post("/api/workspaces/<workspace_id>/test")
    def test_workspace(workspace_id: str):
        ws = require_workspace(workspace_id)
        body = json_body()
        # allow testing with freshly typed credentials before saving
        if body.get("secrets"):
            data = ws.to_api()
            data["secrets"] = {
                k: v for k, v in body["secrets"].items() if v and v != REDACTED_SENTINEL
            } or ws.secrets
            ws = service.workspaces.update(workspace_id, {"secrets": data["secrets"]})
        result = backend_for(ws).test_connection()
        return jsonify(result)

    # -- browsing -------------------------------------------------------------------

    @app.get("/api/workspaces/<workspace_id>/objects")
    def list_objects(workspace_id: str):
        ws = require_workspace(workspace_id)
        service.workspaces.touch(ws.id)
        prefix = request.args.get("prefix", "")
        backend = backend_for(ws)
        files, dirs = backend.list_objects(prefix)
        return jsonify(
            prefix=prefix,
            files=[_entry_json(f, ws.kind) for f in files],
            dirs=[d.key for d in dirs],
        )

    @app.get("/api/workspaces/<workspace_id>/file")
    def file_info(workspace_id: str):
        ws = require_workspace(workspace_id)
        path = _required_param("path")
        backend = backend_for(ws)
        entry = backend.get(path)
        cached = service.cache.get_entry(ws.id, path)
        return jsonify(
            path=path,
            entry=_entry_json(entry, ws.kind),
            category=category_for(path, mime_for(path)),
            language=hljs_language(path),
            cache={
                "cached": bool(cached and Path(cached.local_path).exists()),
                "cached_at": cached.cached_at if cached else None,
                "cached_etag": cached.etag if cached else None,
                "sync_available": service.cache.is_stale(ws.id, path, backend),
            },
        )

    @app.post("/api/workspaces/<workspace_id>/open")
    def open_file(workspace_id: str):
        """Ensure the file is in the local cache and return how to view it."""
        ws = require_workspace(workspace_id)
        path = _required_param("path", json=True)
        backend = backend_for(ws)
        entry, downloaded = service.cache.ensure_cached(ws.id, path, backend)
        return jsonify(
            path=path,
            raw_url=f"/api/workspaces/{ws.id}/raw?path={_q(path)}",
            downloaded=downloaded,
            category=category_for(path, mime_for(path)),
            language=hljs_language(path),
            entry=_entry_json(entry, ws.kind),
        )

    @app.post("/api/workspaces/<workspace_id>/check-versions")
    def check_versions(workspace_id: str):
        ws = require_workspace(workspace_id)
        paths = json_body().get("paths") or []
        if not isinstance(paths, list) or len(paths) > 500:
            raise ApiError("Provide 'paths' as a list of up to 500 keys")
        return jsonify(versions=service.cache.check_versions(ws.id, paths, backend_for(ws)))

    @app.post("/api/workspaces/<workspace_id>/sync")
    def sync_file(workspace_id: str):
        """Force a re-download of a file that changed upstream."""
        ws = require_workspace(workspace_id)
        path = _required_param("path", json=True)
        service.cache.remove_entry(ws.id, path)
        backend = backend_for(ws)
        entry, _ = service.cache.ensure_cached(ws.id, path, backend)
        return jsonify(ok=True, path=path, entry=_entry_json(entry, ws.kind))

    @app.post("/api/workspaces/<workspace_id>/evict")
    def evict_file(workspace_id: str):
        ws = require_workspace(workspace_id)
        path = _required_param("path", json=True)
        service.cache.remove_entry(ws.id, path)
        return jsonify(ok=True)

    # -- raw content ---------------------------------------------------------------

    @app.get("/api/workspaces/<workspace_id>/raw")
    def raw_file(workspace_id: str):
        """Serve file bytes from the cache (downloading first when needed).

        Supports single HTTP Range requests so PDF, audio and video can seek.
        """
        ws = require_workspace(workspace_id)
        path = _required_param("path")
        backend = backend_for(ws)
        cached, _ = service.cache.ensure_cached(ws.id, path, backend)
        file_path = Path(cached.local_path)
        if not file_path.exists():
            raise ApiError("Cached file is missing", 500)
        mime = mime_for(path)
        range_header = request.headers.get("Range")
        if range_header and range_header.startswith("bytes="):
            response = _range_response(file_path, mime, range_header)
        else:
            response = send_file(file_path, mimetype=mime, conditional=True)
        response.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
        response.headers["Content-Disposition"] = _inline_disposition(path)
        return response

    @app.get("/api/workspaces/<workspace_id>/download")
    def download_file(workspace_id: str):
        ws = require_workspace(workspace_id)
        path = _required_param("path")
        backend = backend_for(ws)
        cached, _ = service.cache.ensure_cached(ws.id, path, backend)
        return send_file(
            Path(cached.local_path),
            mimetype=mime_for(path),
            as_attachment=True,
            download_name=os.path.basename(path),
        )

    # -- search ----------------------------------------------------------------------

    @app.get("/api/workspaces/<workspace_id>/search")
    def search(workspace_id: str):
        ws = require_workspace(workspace_id)
        query = (request.args.get("q") or "").strip().lower()
        if not query:
            return jsonify(results=[])
        entries = backend_for(ws).list_all(request.args.get("prefix", ""))
        results = [_entry_json(e, ws.kind) for e in entries if query in e.key.lower()][:200]
        return jsonify(results=results, truncated=len(entries) >= 20000)

    # -- local write operations (writable local workspaces only) -----------------------

    @app.put("/api/workspaces/<workspace_id>/file")
    def write_file(workspace_id: str):
        ws = require_workspace(workspace_id)
        body = json_body()
        path = body.get("path")
        if not path:
            raise ApiError("'path' is required")
        content = body.get("content")
        if not isinstance(content, str):
            raise ApiError("'content' must be text")
        backend = backend_for(ws)
        entry = backend.write_file(path, content.encode("utf-8"))
        service.cache.remove_entry(ws.id, path)
        return jsonify(entry=_entry_json(entry, ws.kind))

    @app.post("/api/workspaces/<workspace_id>/folder")
    def create_folder(workspace_id: str):
        ws = require_workspace(workspace_id)
        path = json_body().get("path")
        if not path:
            raise ApiError("'path' is required")
        backend_for(ws).create_folder(path)
        return jsonify(ok=True)

    @app.post("/api/workspaces/<workspace_id>/rename")
    def rename(workspace_id: str):
        ws = require_workspace(workspace_id)
        body = json_body()
        src, dst = body.get("from"), body.get("to")
        if not src or not dst:
            raise ApiError("'from' and 'to' are required")
        backend_for(ws).rename(src, dst)
        service.cache.remove_entry(ws.id, src)
        return jsonify(ok=True)

    @app.delete("/api/workspaces/<workspace_id>/file")
    def delete_file(workspace_id: str):
        ws = require_workspace(workspace_id)
        path = _required_param("path")
        backend_for(ws).delete(path)
        service.cache.remove_entry(ws.id, path)
        return jsonify(ok=True)

    # -- cache & settings -----------------------------------------------------------

    @app.get("/api/cache")
    def cache_info():
        stats = service.cache.stats()
        stats["bytes_on_disk"] = service.data_dir_size()
        stats["home"] = str(service.home.root)
        return jsonify(stats)

    @app.post("/api/cache/clear")
    def cache_clear():
        workspace_id = json_body().get("workspace_id")
        if workspace_id:
            require_workspace(workspace_id)
        removed = service.cache.clear(workspace_id)
        return jsonify(ok=True, removed=removed)

    @app.get("/api/settings")
    def get_settings():
        return jsonify(settings=service.all_settings())

    @app.put("/api/settings")
    def put_settings():
        return jsonify(settings=service.update_settings(json_body()))

    # -- SPA --------------------------------------------------------------------------

    @app.get("/")
    @app.get("/<path:_spa_path>")
    def spa(_spa_path: str = ""):
        if _spa_path.startswith(("api/", "static/")):
            raise ApiError("Not found", 404)
        return render_template("index.html")

    return app


# -- utilities -----------------------------------------------------------------------


def json_body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}



def _set_session_cookie(resp: Response, token: str) -> None:
    resp.set_cookie(
        SESSION_COOKIE, token, httponly=True, samesite="Lax", max_age=12 * 60 * 60
    )


def _required_param(name: str, *, json: bool = False) -> str:
    value = (json_body() if json else request.args).get(name)
    if not value:
        raise ApiError(f"'{name}' is required")
    return value


def _q(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")


def _entry_json(entry, kind: str) -> dict:  # noqa: ANN001 - BlobEntry | CachedFile
    is_dir = bool(getattr(entry, "is_dir", False))
    key = entry.key
    return {
        "key": key,
        "size": entry.size,
        "last_modified": entry.last_modified,
        "etag": entry.etag,
        "is_dir": is_dir,
        "category": None if is_dir else category_for(key),
    }


def _inline_disposition(path: str) -> str:
    from urllib.parse import quote

    name = os.path.basename(path)
    return f"inline; filename*=UTF-8''{quote(name)}"


def _range_response(file_path: Path, mime: str, range_header: str) -> Response:
    """Minimal single-range support (bytes=start-end / bytes=start-)."""
    size = file_path.stat().st_size
    spec = range_header[6:].split(",")[0].strip()
    start_str, _, end_str = spec.partition("-")
    try:
        if start_str:
            start = int(start_str)
            end = min(int(end_str), size - 1) if end_str else size - 1
        else:
            start = max(size - int(end_str), 0)
            end = size - 1
    except ValueError as exc:
        raise ApiError("Invalid Range header", 416) from exc
    if start > end or start >= size:
        raise ApiError("Requested range not satisfiable", 416)
    length = end - start + 1
    with file_path.open("rb") as fh:
        fh.seek(start)
        data = fh.read(length)
    resp = Response(data, status=206, mimetype=mime)
    resp.headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    resp.headers["Accept-Ranges"] = "bytes"
    return resp
