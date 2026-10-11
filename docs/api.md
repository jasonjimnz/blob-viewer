# HTTP API reference

The UI talks to this JSON REST API. Base URL is the server root; all routes are prefixed `/api/`. In locked mode every route except `/api/health`, `/api/session` and `POST /api/auth/login` requires a session cookie (`bv_session`) obtained by login.

Errors are always JSON: `{"error": "message"}` with a meaningful status code.

## Session & auth

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | `{"status":"ok","version":"0.1.0","locked":bool}` |
| GET | `/api/session` | `{locked, authenticated, username, needs_setup, version}` |
| POST | `/api/auth/login` | `{username, password}` → sets session cookie. **First run in locked mode**: pass `{username, password, confirm_password}` to bootstrap the master admin (responds `created: true`). |
| POST | `/api/auth/logout` | Revokes the session |

## Workspaces

| Method | Path | Description |
|---|---|---|
| GET | `/api/workspaces` | List (secrets redacted) |
| POST | `/api/workspaces` | Create. Body: `{name, kind: "s3"\|"local", endpoint, bucket, region, prefix, path_style, local_path, read_only, secrets: {access_key, secret_key}}` |
| GET | `/api/workspaces/{id}` | One workspace |
| PATCH | `/api/workspaces/{id}` | Update any subset. Pass `secrets: {field: "__REDACTED__"}` to keep an existing secret; omitted fields are kept too. |
| DELETE | `/api/workspaces/{id}` | Remove workspace + encrypted secrets + cache index |
| POST | `/api/workspaces/{id}/test` | Connectivity check → `{ok, message}` |

## Browsing

| Method | Path | Description |
|---|---|---|
| GET | `/api/workspaces/{id}/objects?prefix=` | `{files: [{key,size,last_modified,etag,category}], dirs: ["a/","b/"]}` |
| GET | `/api/workspaces/{id}/file?path=` | Metadata + cache state for one file |
| GET | `/api/workspaces/{id}/search?q=&prefix=` | Recursive filename search (max 200 hits) |

## Open / raw / sync

| Method | Path | Description |
|---|---|---|
| POST | `/api/workspaces/{id}/open` | `{path}` → ensures cached; returns `{raw_url, downloaded, category, language, entry}` |
| GET | `/api/workspaces/{id}/raw?path=` | File bytes from cache (downloads if needed). Supports `Range` for PDF/audio/video. |
| GET | `/api/workspaces/{id}/download?path=` | Same, as attachment |
| POST | `/api/workspaces/{id}/check-versions` | `{paths: [...]}` (≤500) → `{versions: {path: {cached, remote, sync_available, remote_etag, cached_etag}}}` |
| POST | `/api/workspaces/{id}/sync` | `{path}` → force re-download of a changed file |
| POST | `/api/workspaces/{id}/evict` | `{path}` → remove from cache |

## Local write operations (writable local workspaces only)

Remote workspaces always answer `403 {"error": "This workspace is read-only"}`.

| Method | Path | Description |
|---|---|---|
| PUT | `/api/workspaces/{id}/file` | `{path, content}` (UTF-8 text) |
| POST | `/api/workspaces/{id}/folder` | `{path}` create folder |
| POST | `/api/workspaces/{id}/rename` | `{from, to}` |
| DELETE | `/api/workspaces/{id}/file?path=` | Delete file or folder |

## Cache & settings

| Method | Path | Description |
|---|---|---|
| GET | `/api/cache` | `{files, bytes, bytes_on_disk, home}` |
| POST | `/api/cache/clear` | `{workspace_id?}` → `{removed: n}` |
| GET | `/api/settings` | All settings + defaults |
| PUT | `/api/settings` | Update a subset (`theme`, `view_mode`, `sort_by`, `sort_dir`) |

## Example

```bash
# login (locked instance) and store cookies
curl -c jar -X POST localhost:8585/api/auth/login \
     -H 'Content-Type: application/json' \
     -d '{"username":"admin","password":"..."}'

# list workspaces
curl -b jar localhost:8585/api/workspaces

# open (download+cache) a file and get its preview URL
curl -b jar -X POST localhost:8585/api/workspaces/$WS/open \
     -H 'Content-Type: application/json' -d '{"path":"docs/readme.md"}'
```
