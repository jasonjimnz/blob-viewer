# Changelog

All notable changes to Blob Viewer are documented here. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows [SemVer](https://semver.org/).

## [0.1.1] — 2026-10-11

### Fixed

- `blob-viewer init` crashed with `AttributeError: 'Namespace' object has no attribute 'name'`
  when reaching the workspace wizard (the init command does not carry workspace flags).

## [0.1.0] — 2026-10-11

First public release.

### Added

- Multiple workspaces: S3-compatible buckets (AWS S3, MinIO, RustFS, Backblaze B2, Cloudflare R2, DigitalOcean Spaces, Wasabi…) and local folders.
- Universal file preview: markdown (sanitised), source code with syntax highlighting (26 languages), PDF (pdf.js), images, audio, video, CSV tables and plain text.
- Local download cache with ETag-based version tracking, "update available" badges and one-click sync. Download-once semantics; offline access to cached files.
- OneDrive/MinIO-style web UI: sidebar workspaces, breadcrumbs, list/grid views, sorting, workspace-wide search, context menus, toasts.
- Eight themes (5 dark, 3 light) switchable live from the UI or CLI.
- Fully vendored frontend (marked, DOMPurify, highlight.js, pdf.js) — no CDN, air-gap friendly.
- Encrypted credential storage (Fernet at rest, redacted everywhere else).
- Locked mode (`--locked`) with master-admin bootstrap, PBKDF2 password hashing and server-side sessions.
- Guided CLI: `init`, `run`, `serve`, `workspace`, `user`, `cache`, `theme`, `doctor`, `version` — interactive and scriptable.
- Desktop app (pywebview) with automatic server-mode fallback.
- Docker image (multi-stage, non-root, ~195 MB) with healthcheck and volume-based persistence.
- Comprehensive docs, HTTP API reference and tests (unit, API, real-S3 e2e, Playwright browser e2e).

[0.1.0]: https://github.com/jasonjimnz/blob-viewer/releases/tag/v0.1.0
