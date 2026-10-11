# Architecture

A tour of the codebase for contributors and the curious.

## The big picture

```
┌─────────────────────────────────────────────────────────────────┐
│  Desktop (pywebview window)  or  Browser                        │
│  ─────────────────────────────────────────                      │
│  Vanilla HTML/JS/CSS SPA (vendored libs, no CDN)                │
│    js/app.js  js/api.js  js/ui.js  js/icons.js                  │
└──────────────────────────────┬──────────────────────────────────┘
                               │ JSON /api/*  (session cookie)
┌──────────────────────────────▼──────────────────────────────────┐
│  Flask app (api.py) — REST endpoints, auth gate, SPA serving    │
│      │                                                          │
│      ▼                                                          │
│  AppService (service.py) — shared container:                    │
│    ├── WorkspaceStore (workspaces.py)  — CRUD + encrypted       │
│    │                                      secrets (secrets.py)  │
│    ├── AuthService (auth.py)           — PBKDF2 + sessions      │
│    ├── CacheManager (cache.py)         — ETag index, sync       │
│    └── Database (db.py)                — SQLite, WAL            │
│                                                                 │
│  Storage backends (storage/)                                    │
│    ├── S3Storage (s3.py)     — boto3, read-only                 │
│    ├── LocalStorage (local.py) — filesystem, writable           │
│    └── factory.py            — workspace → backend              │
└─────────────────────────────────────────────────────────────────┘
```

## Process model

- **Desktop mode** (`blob-viewer run`): starts a threaded Werkzeug server on `127.0.0.1:<free port>` inside the process, then opens a pywebview window pointing at it. One process, window and server.
- **Server mode** (`blob-viewer serve`): a waitress server (production, multi-threaded) on the requested host/port.
- SQLite in WAL mode with a process-wide lock per database instance; safe for concurrent request threads.

## Data layout

```
BLOB_VIEWER_HOME (default ~/.blob-viewer)
├── blob-viewer.db    # settings, users, workspaces, secrets (ciphertext), cache index, sessions
├── secrets.key       # per-installation Fernet key
└── cache/<ws-id>/    # downloaded objects, sha256-named with readable suffix
```

Everything is in one folder: back up = copy; reset = delete.

## Key design decisions

1. **Secrets never cross the API boundary.** `WorkspaceStore._hydrate` decrypts secrets into memory only; `to_api()` returns redacted values (`••••last4`). Updates accept `__REDACTED__` as "keep current", so the UI can round-trip forms without ever seeing real values.
2. **ETag-based cache.** `CacheManager.ensure_cached` compares the cached ETag with a fresh `HeadObject`. Local workspaces use an `mtime_ns+size` fingerprint as a pseudo-ETag. This is what powers download-once and the "update available" badge.
3. **Read-only remote by construction.** The `Storage` base class raises `ReadOnlyError` for all write operations; `S3Storage` never overrides them. Local writes additionally check the `read_only` flag. The API maps `ReadOnlyError` → 403.
4. **No build step frontend.** All JS/CSS is hand-written and vendored libraries are committed under `static/vendor/`. The package works air-gapped and stays diffable.
5. **One storage interface.** `BlobEntry(key, size, last_modified, etag, is_dir)` is the only vocabulary the rest of the app knows — adding e.g. an Azure/GCS backend means implementing `Storage` and adding a branch in `factory.py`.

## Module map

| Module | Responsibility |
|---|---|
| `paths.py` | Home directory resolution, cache paths |
| `db.py` | SQLite schema + connection management |
| `secrets.py` | Fernet encrypt/decrypt, redaction |
| `workspaces.py` | Workspace model + CRUD + validation |
| `auth.py` | Master admin, PBKDF2, sessions |
| `cache.py` | Cache index, ensure_cached, staleness, clear |
| `preview.py` | Filename/MIME → category + highlight.js language |
| `themes.py` | Theme registry shared by CLI and UI |
| `storage/` | Backends (base, s3, local, factory) |
| `api.py` | Flask app: routes, auth gate, error mapping |
| `server.py` | Server lifecycle, port discovery, banner |
| `desktop.py` | pywebview window + locked-mode bootstrap |
| `cli.py` | argparse commands + rich wizards |
| `service.py` | AppService container |

## Tests

```
tests/test_core.py           unit: secrets, workspaces, storage, cache, auth, preview
tests/test_api.py            API: Flask test client, locked mode, 403s, ranges
tests/test_e2e_rustfs.py     e2e: real S3 server (RustFS) on localhost:9000
tests/test_e2e_browser.py    e2e: Playwright Chromium driving the real UI
```

Run everything with `pytest -m e2e tests/`. The real-S3 e2e tests target a local RustFS/MinIO instance at `http://localhost:9000` (default credentials `rustfsadmin/rustfsadmin`, bucket `blob-viewer-test`; fixtures are created automatically). If your instance differs, override any of `BLOB_VIEWER_E2E_S3_ENDPOINT`, `BLOB_VIEWER_E2E_S3_ACCESS`, `BLOB_VIEWER_E2E_S3_SECRET`, `BLOB_VIEWER_E2E_S3_BUCKET`.
