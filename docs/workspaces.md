# Workspaces

A *workspace* is a named source of files. You can register as many as you want and switch between them instantly. Two kinds exist:

## S3 workspaces (remote, read-only)

Work with any S3-compatible service:

| Service | Endpoint URL |
|---|---|
| AWS S3 | `https://s3.<region>.amazonaws.com` |
| MinIO / RustFS (self-hosted) | `http://host:9000` |
| Backblaze B2 | `https://s3.<region>.backblazeb2.com` |
| Cloudflare R2 | `https://<account>.r2.cloudflarestorage.com` |
| DigitalOcean Spaces | `https://<region>.digitaloceanspaces.com` |
| Wasabi | `https://s3.<region>.wasabisys.com` |

Fields:

- **Name** — how it appears in the sidebar.
- **Endpoint URL** — the API root of the service.
- **Bucket** — the bucket to browse.
- **Region** — optional; defaults to `us-east-1` (correct for MinIO/RustFS and most S3 clones).
- **Root prefix** — optional; browse only a sub-path of the bucket (e.g. `projects/2025/`).
- **Access key / Secret key** — stored encrypted (see below). Leave both empty for public/anonymous buckets.
- **Path-style addressing** — on by default. Path style (`http://host:9000/bucket`) is required by MinIO, RustFS, B2 and R2. Virtual-host style (`bucket.s3.amazonaws.com`) is what AWS uses; Blob Viewer's default works there too through the endpoint URL form above.

Remote workspaces are **read-only by design**: files are downloaded to your cache for viewing but Blob Viewer will never create, modify or delete anything in the bucket — every write API returns `403`.

### Adding via CLI (non-interactive)

```bash
blob-viewer workspace add \
  --kind s3 --name documents \
  --endpoint https://s3.us-east-1.amazonaws.com \
  --bucket documents --region us-east-1 \
  --access-key AKIA... --secret-key ...
```

### Credential handling

- Keys are encrypted with **Fernet** (AES-128-CBC + HMAC) using a random key generated per installation and stored in `<home>/secrets.key` (chmod 600 on POSIX).
- Ciphertext lives in the SQLite database; plain text never touches disk.
- The API and CLI *never* print secret values — only masked hints like `••••ab12`. Editing a workspace leaves existing secrets untouched unless you type new ones.

## Local workspaces (private, writable)

Point Blob Viewer at any folder on your machine:

```bash
blob-viewer workspace add --kind local --name notes --local-path ~/Documents/notes
```

- Fully **writable** (unless you tick *read-only*): create folders, create/edit text files, rename, delete — from the UI.
- Never leaves your machine; no credentials involved.
- **Path rules**: absolute paths and `~` are used as given; *relative* paths
  (e.g. `./notes`) resolve against the Blob Viewer home (`~/.blob-viewer/notes`),
  keeping workspaces inside the application's data folder. A missing folder is
  offered to be created during the wizard (created automatically in scripts).
- Files are fingerprinted by `mtime+size` instead of S3 ETags, so version detection still works.

## Managing workspaces

```bash
blob-viewer workspace list              # table overview
blob-viewer workspace show documents    # details (secrets redacted)
blob-viewer workspace test documents    # connectivity check
blob-viewer workspace edit documents    # guided edit
blob-viewer workspace remove documents  # remove + purge its cache
```

Everything is also available in the UI: **Settings → Workspaces**, or right-click a workspace in the sidebar.

Removing a workspace deletes its configuration, encrypted secrets and cached files. Remote data is never touched.
