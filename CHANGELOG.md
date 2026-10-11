# Changelog

All notable changes to Blob Viewer are documented here. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows [SemVer](https://semver.org/).

## [0.1.5] — 2026-10-11

### Fixed

- Preview modals did not scroll: the renderer swapped the wrapper's className,
  dropping the layout classes, and the caller-provided wrapper inside `.modal`
  was not a constrained flex column, so content grew past the modal and was
  clipped. Preview classes are now applied additively (setPreviewClass) and
  `.modal > div` is a bounded flex column; `.modal-body` gets `min-height: 0`.
- Verified scroll for markdown, code and CSV previews; short files still fit
  without scrollbars. Regression-tested in the browser e2e.

## [0.1.4] — 2026-10-11

### Fixed

- Modal headers rendered as the literal text “[object HTMLDivElement]”: the
  modal-head helper returned a DOM element that was interpolated into an HTML
  template string. It now returns an HTML string; the close button is bound
  via data-attribute. Affected every modal (file preview, settings, confirm,
  workspace form).

### Improved

- Markdown preview is defensive: awaited/handled non-string renderer output,
  explicit error when the vendored libraries fail to load, and a source
  fallback so a broken render never leaves a blank pane.
- Text decoding falls back to windows-1252 for non-UTF-8 files.
- Unexpected JS errors now surface as toasts instead of failing silently.
- Browser e2e regression test asserts the modal head shows the real title.

## [0.1.3] — 2026-10-11

### Fixed

- Desktop mode crashed on launch: `create_window()` received an invalid
  `background` argument — the correct pywebview parameter is `background_color`.

## [0.1.2] — 2026-10-11

### Fixed

- Local-workspace folder paths are now normalised to absolute: relative paths
  (e.g. `./local`) resolve against the **application home** (`~/.blob-viewer/local`),
  never against the current working directory.
- The workspace wizard offers to create a missing folder instead of saving a
  workspace that cannot open (created automatically in non-interactive use).
- Republished the package so installs contain the current source.

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
