# Troubleshooting & FAQ

## Installation

**`blob-viewer` command not found** — ensure the Python `Scripts`/`bin` directory of your venv is on PATH, or use `python -m blob_viewer.cli`.

**Desktop window doesn't open** — `blob-viewer doctor` shows pywebview status. Without a GUI, Blob Viewer automatically falls back to server mode and prints the URL. On Linux install GTK webkit (`sudo apt install python3-gi gir1.2-webkit2-4.1`).

## Workspaces

**"Access denied: check the workspace credentials"** — run `blob-viewer workspace test NAME`. Common causes: wrong secret, key rotated, or the endpoint needs path-style addressing (MinIO/RustFS/R2/B2 — it is on by default). If the endpoint is `localhost` inside Docker, use `host.docker.internal` instead.

**My bucket is on AWS and listing is slow** — leave path-style off is fine, but specify the correct region; otherwise every request travels to `us-east-1` first.

**Can I browse only a subfolder of a bucket?** — set the *Root prefix* (e.g. `projects/2025/`); navigation is then rooted there.

**Someone typed a wrong secret. Where do I fix it?** — `blob-viewer workspace edit NAME` or UI right-click → Settings. Old values stay until you replace them.

## Cache

**Where are cached files?** — `Settings → Cache` shows the folder; default `~/.blob-viewer/cache/`.

**A file shows "update" but I know it didn't change** — S3 ETags can differ for re-uploaded identical content on multipart uploads. Click sync once; the badge clears.

**Disk usage** — `blob-viewer cache stats`. Clear per workspace or entirely; nothing remote is affected.

## Locked mode

**Locked out?** — physical/CLI access is enough: `blob-viewer user reset`. All sessions are revoked on reset.

**Sessions expire after 12 hours** — by design. Re-login.

## FAQ

**Why is it read-only for S3?** — Blob Viewer is a *viewer*. Personal S3 hygiene means your browser session should never be able to delete bucket contents. Local workspaces are fully writable instead.

**Does it phone home?** — No. No telemetry, no CDNs, no update checkers. Traffic = your S3 endpoints only.

**Multiple users?** — It's designed for one person. Locked mode adds a single master admin; the data folder is per-OS-user anyway. Run separate instances with different `BLOB_VIEWER_HOME`s if you share a machine.

**Where is my data?** — One folder (`~/.blob-viewer`): database, encryption key, cache. Backup = copy the folder (see [Docker deployment](docker.md) for volumes).

**Can I add Azure Blob / GCS?** — Yes: implement the small `Storage` interface (`storage/base.py`) and register it in `storage/factory.py`. `S3Storage` already covers most services because they speak the S3 API.

**Windows shows weird characters in the CLI** — fixed automatically: the CLI forces UTF-8 output on legacy consoles.

**Is there a web demo?** — No hosted demo (it's a personal, local-first tool), but Docker gets you one in under a minute.
