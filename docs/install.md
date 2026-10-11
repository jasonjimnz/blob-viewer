# Installation

## Requirements

- **Python 3.11+** (3.13 recommended)
- Any OS: Windows, macOS, Linux

## pip

```bash
pip install blob-viewer
```

This installs the CLI, the Flask server, the desktop shell (pywebview) and all Python dependencies.

### Desktop window support (Linux only)

pywebview needs a native webview. On Windows and macOS nothing extra is required. On Linux:

```bash
# Debian / Ubuntu (GTK backend)
sudo apt install python3-gi gir1.2-webkit2-4.1
```

If a GUI is unavailable (SSH box, container, WSL without GUI), Blob Viewer automatically falls back to server mode — everything works in your normal browser.

## Isolated / air-gapped environments

Blob Viewer was designed to run without internet access after installation:

- The entire frontend (JS/CSS, markdown renderer, syntax highlighter, PDF viewer) is **vendored** inside the package under `static/vendor/` — no CDN calls at runtime.
- The only outbound traffic is to the S3 endpoints of your own workspaces.
- To install offline, download the wheel once (`pip download blob-viewer -d wheels/`), copy the folder to the target machine and `pip install --no-index --find-links wheels/ blob-viewer`.

## Docker

```bash
docker pull ghcr.io/jasonjimnz/blob-viewer:latest
docker run -d --name blob-viewer -p 8585:8585 -v blob-viewer-data:/data ghcr.io/jasonjimnz/blob-viewer:latest
```

See [Docker deployment](docker.md) for the full guide.

## From source

```bash
git clone https://github.com/jasonjimnz/blob-viewer.git
cd blob-viewer
python -m venv .venv
.venv/Scripts/pip install -e .[dev]     # POSIX: .venv/bin/pip
```

## Verify

```bash
blob-viewer doctor
```

checks Python version, all optional components, data directory writability and more.
