# CLI reference

All commands accept `--home DIR` to use a custom data directory, and `blob-viewer --help` shows the full tree. Non-interactive use: every prompt has a flag equivalent; when stdin is not a TTY the CLI fails loudly instead of hanging.

## `blob-viewer init`

Guided first-run configuration: optionally creates the master admin (`--locked`), adds the first workspace, prints next steps.

```bash
blob-viewer init [--locked]
```

## `blob-viewer run`

Launches the desktop app (pywebview window) with an internal server on `127.0.0.1`.

```bash
blob-viewer run [--locked] [--port N]
```

Falls back to server mode if no GUI is available.

## `blob-viewer serve`

Headless production server (waitress).

```bash
blob-viewer serve [--locked] [--host 127.0.0.1] [--port 8585] [--open]
```

`--open` launches your browser after startup.

## `blob-viewer workspace`

| Command | Description |
|---|---|
| `workspace add` | Guided wizard. Non-interactive flags: `--kind s3\|local --name --endpoint --bucket --region --prefix --path-style --access-key --secret-key --local-path --read-only` |
| `workspace list [--json]` | Table (or JSON) of all workspaces |
| `workspace show NAME` | Details; secrets always redacted |
| `workspace test NAME` | Connectivity check, exit code 1 on failure |
| `workspace edit NAME` | Guided edit of endpoint/bucket/credentials/path |
| `workspace remove NAME [-y]` | Remove workspace + purge its cache |

## `blob-viewer user`

Master admin management for locked mode.

| Command | Description |
|---|---|
| `user create [--username --password]` | Create the admin (fails if one exists) |
| `user reset [--username --password]` | Replace the admin, revoking all sessions |
| `user status` | Whether an admin is configured |

## `blob-viewer cache`

| Command | Description |
|---|---|
| `cache stats` | Files, bytes, per-workspace breakdown |
| `cache clear [--workspace NAME] [-y]` | Delete cached files |

## `blob-viewer theme`

| Command | Description |
|---|---|
| `theme list` | All themes with mode/accent, current marked |
| `theme set NAME` | Set the default theme (e.g. `nord`, `paper`) |

## `blob-viewer doctor`

Diagnostics: Python version, boto3/pywebview/cryptography/waitress presence, data directory writability, key/database presence. Exit code 1 if anything required is missing.

## `blob-viewer version`

Version and Python info.

## Exit codes

`0` success · `1` operation failed (bad credentials, unknown name, doctor failure) · `130` interrupted.
