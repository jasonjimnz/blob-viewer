# Files, preview & the cache

## Supported previews

| Category | Extensions | How it renders |
|---|---|---|
| Markdown | `.md .markdown .mdx` | rendered HTML (marked + DOMPurify sanitising), code blocks highlighted |
| Code | `.py .js .ts .go .rs .java .c .cpp .cs .sh .sql .tf` and 40+ more | syntax-highlighted via highlight.js (26 languages bundled) |
| PDF | `.pdf` | pdf.js with page navigation |
| Images | `.png .jpg .gif .webp .svg .bmp .ico .avif` | inline with zoom-friendly layout |
| Audio | `.mp3 .wav .ogg .flac .m4a .opus` | native player with seeking |
| Video | `.mp4 .webm .mkv .mov` | native player with seeking |
| CSV / TSV | `.csv .tsv` | scrollable table, sticky header, numeric alignment |
| Text | `.txt .log .ini .yaml .toml .json` … | plain text |
| Binary | everything else (`.exe .zip …`) | no inline preview; one-click download |

Raw serving supports **HTTP range requests**, which is what makes PDF paging and audio/video seeking work without downloading whole files.

## The download cache

Every file you open is stored under `<home>/cache/<workspace>/` and indexed in SQLite with its remote **ETag** (or a local mtime fingerprint for local workspaces):

```
~/.blob-viewer/
└── cache/
    └── a1b2c3…/            # one folder per workspace
        ├── 9f8e7d…-readme.md
        └── 5c4b3a…-diagram.pdf
```

Rules:

1. **Download once.** Opening a cached file with a matching ETag serves it from disk — no network call at all.
2. **Detect change.** While you browse, Blob Viewer batches a version check for visible files. Changed files get an `update` badge (amber).
3. **Sync on demand.** Clicking the badge (or *Sync* in the context menu) re-downloads that one file.
4. **Offline friendly.** Cached files open fine with the remote unreachable — you'll only get an error if you try to sync.

### Managing the cache

```bash
blob-viewer cache stats              # per-workspace usage
blob-viewer cache clear              # everything (asks first)
blob-viewer cache clear --workspace documents
```

Or in the UI: **Settings → Cache** shows totals, the storage folder and per-workspace clear buttons. Individual files can be evicted from the file context menu (*Remove from cache*).

Cache entries whose files were already deleted by the OS are detected and refreshed automatically.

## Downloads

The *Download* action always gives you the original bytes as an attachment — the same cached copy, re-fetched only if stale. Use it for files without an inline preview or to save a local copy.
