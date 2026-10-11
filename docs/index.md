# Blob Viewer documentation

**A personal S3/MinIO bucket browser and file previewer** — by Jason Jiménez Cruz.

Blob Viewer connects to any S3-compatible bucket (AWS S3, MinIO, RustFS, Backblaze B2, Cloudflare R2, DigitalOcean Spaces, Wasabi…) or a local folder and gives you a fast, modern file browser with previews for almost anything: markdown, source code, PDFs, images, audio, video, CSV and plain text. Every file you open is cached locally so your workspace is always there — even offline — and nothing is downloaded twice.

## Documentation index

| Document | What it covers |
|---|---|
| [Installation](install.md) | pip install, desktop requirements, Docker, isolated environments |
| [Getting started](getting-started.md) | First run, the guided `init`, daily usage |
| [Workspaces](workspaces.md) | S3 and local workspaces, credentials, multiple accounts |
| [Files, preview & cache](preview-cache.md) | Supported types, how the cache works, sync detection |
| [Security & locked mode](security.md) | Credential encryption, redaction, master admin, login |
| [CLI reference](cli.md) | Every command and flag |
| [HTTP API reference](api.md) | The REST API powering the UI (useful for scripting) |
| [Themes & customisation](themes.md) | All themes, how to add your own |
| [Docker deployment](docker.md) | Image, volumes, compose, reverse proxies |
| [Architecture](architecture.md) | How the code is organised and why |
| [Troubleshooting & FAQ](faq.md) | Common problems and answers |

## The 60-second version

```bash
pip install blob-viewer
blob-viewer init      # guided: create a workspace, pick a theme
blob-viewer run       # native desktop window
```

Or headless:

```bash
blob-viewer serve --host 0.0.0.0 --port 8585   # then open http://host:8585
```

Or Docker:

```bash
docker run -d -p 8585:8585 -v blob-viewer-data:/data ghcr.io/jasonjimnz/blob-viewer:latest
```

## Design principles

1. **Personal first** — one user, no accounts or teams. Locked mode adds a single master admin when you need it.
2. **Read-only remote** — remote buckets are never modified. Blob Viewer downloads, previews and caches; your S3 data stays untouched.
3. **Local cache as your workspace** — once a file is opened it lives in your local cache, available offline and never re-downloaded until it actually changes upstream.
4. **No network surprises** — the frontend is plain HTML/JS/CSS with vendored libraries. No CDN calls, no telemetry, works air-gapped.
5. **Credentials never leave the machine** — encrypted at rest, redacted in every API response.
