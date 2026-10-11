# Getting started

## First run: `blob-viewer init`

The guided wizard walks you through everything:

```text
$ blob-viewer init
╭──────────────────────────────────────────╮
│  Blob Viewer v0.1.0                      │
│  A personal S3/MinIO bucket browser...   │
╰──────────────────────────────────────────╯
Data directory: /home/you/.blob-viewer

Add your first workspace now? [Y/n]:
Workspace kind [s3/local]: s3
Workspace name: my-bucket
Endpoint URL [http://localhost:9000]: https://s3.us-east-1.amazonaws.com
Bucket name: documents
Region []: us-east-1
Access key []: AKIA...
Secret key: ********
✓ Workspace 'my-bucket' created
✓ Bucket 'documents' is reachable
```

Every prompt accepts Enter for the default, and everything can also be done non-interactively (see the [CLI reference](cli.md)) — useful for scripting and containers.

## Daily use

### Desktop app

```bash
blob-viewer run
```

opens a native window with the full UI. The server binds to `127.0.0.1` on a free port; only the window talks to it.

### Server mode

```bash
blob-viewer serve                    # http://127.0.0.1:8585
blob-viewer serve --host 0.0.0.0     # reachable from your network — see below
```

Server mode uses the production-grade waitress server. When you bind to `0.0.0.0` anyone on your network can read your workspaces unless you enable **locked mode**:

```bash
blob-viewer serve --host 0.0.0.0 --locked
```

See [Security & locked mode](security.md).

## Using the UI

- **Left sidebar** — all your workspaces; right-click one for settings, cache and delete actions.
- **Breadcrumb bar** — navigate folders; click any level to jump back.
- **File list / grid** — toggle with the toolbar button; click column headers to sort. Click a folder to enter, a file to preview.
- **Status badges** — `remote` (not downloaded yet), `cached` (local copy, up to date), `update` (a newer version exists upstream — click the badge to sync).
- **Search box** — searches the whole current workspace from any folder.
- **Right-click a file** — preview, download, sync, evict from cache, copy path; on writable local workspaces also rename and delete.
- **Settings** (gear icon) — themes, cache management, workspace management, security info.

## What happens when I open a file?

1. Blob Viewer checks the local cache index (SQLite).
2. If the file is cached and its ETag matches upstream → served instantly from disk.
3. Otherwise it downloads once, records the ETag, then serves it.
4. Whenever you browse, background version checks flag files whose upstream version changed with an `update` badge.

So your machine accumulates exactly the files you actually viewed — your personal workspace mirror — and stale copies are refreshed only when they really changed. See [Files, preview & cache](preview-cache.md).
