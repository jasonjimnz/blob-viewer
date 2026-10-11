# Docker deployment

## Image

```bash
docker pull ghcr.io/jasonjimnz/blob-viewer:latest
```

- **Multi-stage build**: wheels are compiled in a builder stage and only the clean virtualenv is copied into the runtime — no build tools, no pip cache.
- Runs as **non-root** user (`blobviewer`, uid/gid 1000).
- State lives in the `/data` volume (`BLOB_VIEWER_HOME=/data`).
- Server mode only — the container has no desktop shell.

## Quick start

```bash
docker run -d --name blob-viewer \
  -p 8585:8585 \
  -v blob-viewer-data:/data \
  ghcr.io/jasonjimnz/blob-viewer:latest
```

## Locked mode

```bash
docker run -d -p 8585:8585 -v blob-viewer-data:/data \
  ghcr.io/jasonjimnz/blob-viewer:latest \
  serve --locked --host 0.0.0.0 --port 8585
```

The first visit shows the master-admin setup form; create it and log in.

## docker-compose

```yaml
services:
  blob-viewer:
    image: ghcr.io/jasonjimnz/blob-viewer:latest
    ports: ["8585:8585"]
    volumes: ["blob-viewer-data:/data"]
    # command: ["serve", "--locked", "--host", "0.0.0.0", "--port", "8585"]
    restart: unless-stopped

volumes:
  blob-viewer-data:
```

## Reaching your S3 endpoints

The container can reach any endpoint reachable from the Docker host. For S3 services on `localhost` of the host itself, use `http://host.docker.internal:9000` (Docker Desktop) or the host's LAN IP.

## Backups

Everything — database, encryption key, cache — is inside the `blob-viewer-data` volume. Back it up as a whole:

```bash
docker run --rm -v blob-viewer-data:/data -v $PWD:/backup alpine \
  tar czf /backup/blob-viewer-backup.tar.gz -C /data .
```

Restoring = extracting the archive back into the volume. The encryption key travels with the backup, so it restores cleanly on any machine.

## Reverse proxy (TLS)

Any proxy works; the app is a plain HTTP service. Example Caddy:

```
blob.example.com {
    reverse_proxy blob-viewer:8585
}
```

Always enable `--locked` when exposing beyond localhost.
