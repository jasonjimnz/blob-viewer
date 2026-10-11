# Blob Viewer

**A personal S3/MinIO bucket browser and file previewer.**

Blob Viewer connects to any S3-compatible bucket — AWS S3, MinIO, Backblaze B2, Cloudflare R2, DigitalOcean Spaces, Wasabi — or to a plain local folder, and gives you a fast, modern file browser with previews for markdown, source code, PDFs, images, audio, video, CSV and more. Every file you open is cached locally, so your workspace is always available — even offline — and nothing is downloaded twice.

> Built for personal use by [Jason Jiménez Cruz](https://github.com/jasonjimnz).

## Highlights

- **Many workspaces** — register as many S3 buckets or local folders as you want and switch between them instantly.
- **Universal preview** — markdown, code with syntax highlighting, PDF, images, audio, video, CSV tables, plain text. Anything else is one click away as a download.
- **Local download cache** — files are fetched once and reused. When a newer version exists upstream, Blob Viewer tells you and lets you sync.
- **Remote workspaces are read-only** — blobs are never modified in place. Local workspaces stay fully writable.
- **Encrypted credentials** — access keys are encrypted at rest and always redacted in the UI and API; nobody can read them back from a config dump.
- **Locked mode** — start with `--locked` to require a master-admin login in the desktop app and the server.
- **Runs anywhere** — as a desktop app (pywebview), a headless server, or a small Docker container. The frontend is plain HTML/JS/CSS with vendored libraries: no CDN, no build step, works in isolated environments.
- **Many themes** — dark, light and coloured themes switchable from the UI.

## Install

```bash
pip install blob-viewer
```

Python 3.11+ (3.13 recommended). For the desktop window on Linux you may need GTK/Qt libraries (`sudo apt install python3-gi gir1.2-webkit2-4.1` on Debian/Ubuntu); on Windows and macOS there are no extra requirements. If a GUI is unavailable, use server mode — everything works in the browser.

## Quick start

```bash
# guided setup: create your first workspace, pick a theme
blob-viewer init

# open the desktop app
blob-viewer run

# or serve it on the network (e.g. a home server / container)
blob-viewer serve --host 0.0.0.0 --port 8585
```

Then open <http://127.0.0.1:8585> if you used `serve`.

### Locked mode

```bash
# first run asks you to create the master admin
blob-viewer run --locked

# CLI login is enforced in the desktop app and the server
blob-viewer serve --locked
```

## Managing workspaces

```bash
blob-viewer workspace add          # guided wizard (S3 or local)
blob-viewer workspace list
blob-viewer workspace test my-bucket
blob-viewer workspace remove my-bucket
```

Or do everything from the UI: **Settings → Workspaces → Add workspace**.

| Field | S3 workspace | Local workspace |
|---|---|---|
| Endpoint | `https://s3.amazonaws.com`, `http://localhost:9000`, ... | — |
| Bucket | required | — |
| Access / Secret key | encrypted at rest | — |
| Region | optional (`us-east-1` default) | — |
| Prefix | optional root path inside the bucket | — |
| Path style | on by default (MinIO/R2/B2) | — |
| Folder | — | any local path |
| Writable | never (read-only by design) | yes |

## CLI overview

```
blob-viewer init                     Guided first-run configuration
blob-viewer run [--locked] [--port]  Launch the desktop app
blob-viewer serve [--locked]         Headless server mode
blob-viewer workspace add|list|show|test|remove|edit
blob-viewer user create|reset|status Master admin for locked mode
blob-viewer cache stats|clear        Inspect / empty the download cache
blob-viewer theme list|set           Change the UI theme
blob-viewer doctor                   Diagnose installation problems
blob-viewer version                  Show version
```

Run `blob-viewer <command> --help` for details on every command.

## Where is my data?

Everything lives in one folder (default `~/.blob-viewer`, override with `BLOB_VIEWER_HOME` or `--home`):

```
~/.blob-viewer/
├── blob-viewer.db    # workspaces, settings, cache index (secrets encrypted)
├── secrets.key       # per-installation encryption key (chmod 600)
└── cache/            # downloaded files, one folder per workspace
```

Delete the folder = factory reset. Credentials are encrypted with a key that never leaves your machine; the API never returns secret values, only masked hints like `••••ab12`.

## Docker

```bash
docker run -d --name blob-viewer \
  -p 8585:8585 -v blob-viewer-data:/data \
  ghcr.io/jasonjimnz/blob-viewer:latest
```

The image is multi-stage, runs as a non-root user and stores state in the `/data` volume. `--locked` is honoured via the `BLOB_VIEWER_LOCKED=1` environment variable or the container command.

## Documentation

Full documentation lives in [`docs/`](docs/index.md):

- [Installation](docs/install.md)
- [Getting started](docs/getting-started.md)
- [Workspaces](docs/workspaces.md)
- [File preview & the cache](docs/preview-cache.md)
- [Security & locked mode](docs/security.md)
- [CLI reference](docs/cli.md)
- [HTTP API reference](docs/api.md)
- [Themes & customisation](docs/themes.md)
- [Docker deployment](docs/docker.md)
- [Architecture](docs/architecture.md)
- [Troubleshooting / FAQ](docs/faq.md)

## Development

```bash
git clone https://github.com/jasonjimnz/blob-viewer.git
cd blob-viewer
python -m venv .venv && .venv/Scripts/pip install -e .[dev]   # POSIX: .venv/bin/pip
pytest            # unit tests
pytest -m e2e     # end-to-end tests (needs Docker; uses a throwaway MinIO)
```

See [docs/architecture.md](docs/architecture.md) for a tour of the codebase and how the pieces fit together.

## License

[MIT](LICENSE) © Jason Jiménez Cruz
