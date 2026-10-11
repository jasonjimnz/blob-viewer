# Security & locked mode

Blob Viewer is a personal tool. Its default posture is safe for that use case, and locked mode hardens it for network exposure.

## Defaults

- `blob-viewer run` and `blob-viewer serve` bind to **127.0.0.1** — nothing leaves your machine.
- Credentials are **encrypted at rest**; the UI/API only ever shows masked hints (`••••ab12`).
- Remote workspaces are **read-only**; write endpoints answer `403`.
- No telemetry, no external calls except to your own configured S3 endpoints.
- Sessions (locked mode) are opaque server-side tokens with a 12-hour expiry, sent as `HttpOnly`, `SameSite=Lax` cookies.

## Credential encryption

```
<home>/secrets.key      ← random Fernet key, generated once, chmod 600
<home>/blob-viewer.db   ← secrets stored as Fernet ciphertext
```

Whoever can read `secrets.key` (the OS user running Blob Viewer) can decrypt the database — that's the trust boundary, same as ssh keys or browser password stores. Other local users cannot. Losing the key means re-entering workspace credentials (config and cache survive).

## Locked mode

Start with `--locked` to require login in the desktop app **and** the server:

```bash
blob-viewer run --locked
blob-viewer serve --host 0.0.0.0 --locked
```

First run in locked mode asks you to create the **master admin** (username + password ≥ 8 chars, PBKDF2-HMAC-SHA256, 210k iterations, per-password salt). The password hash is stored locally; nothing is ever sent anywhere.

You can also create it ahead of time:

```bash
blob-viewer user create                 # interactive
blob-viewer user create --username admin --password ...   # scripted
blob-viewer user reset                  # replace it (revokes all sessions)
blob-viewer user status
```

In locked mode:

- The UI shows a login screen (and a first-run setup form when no admin exists yet).
- Every API call requires a valid session — including from the desktop shell.
- `POST /api/auth/login` with wrong credentials fails closed; enumeration is mitigated with constant-time comparisons.

## Exposing to a network — checklist

1. Always run `serve --locked` when binding to anything but localhost.
2. Keep the data directory (`BLOB_VIEWER_HOME`) private to the service user.
3. Prefer TLS: put the container behind a reverse proxy (Caddy, Traefik, nginx) — see [Docker deployment](docker.md).
4. Anonymous S3 workspaces expose whatever the bucket exposes; they are read-only but consider who can reach your instance.
