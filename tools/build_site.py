#!/usr/bin/env python
"""Build the GitHub Pages site into site/.

Renders docs/*.md to styled HTML and generates a landing page.
Dev-only tool: requires the `markdown` package (pip install blob-viewer[dev]).
"""
from __future__ import annotations

import datetime
import pathlib
import re
import shutil

import markdown

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
OUT = ROOT / "site"

MD = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "codehilite"],
                       extension_configs={"codehilite": {"guess_lang": False, "noclasses": False}})

NAV = [
    ("index.md", "Introduction"),
    ("install.md", "Installation"),
    ("getting-started.md", "Getting started"),
    ("workspaces.md", "Workspaces"),
    ("preview-cache.md", "Preview & cache"),
    ("security.md", "Security"),
    ("cli.md", "CLI"),
    ("api.md", "HTTP API"),
    ("themes.md", "Themes"),
    ("docker.md", "Docker"),
    ("architecture.md", "Architecture"),
    ("faq.md", "FAQ"),
]

PAGE_TMPL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Blob Viewer</title>
<meta name="description" content="Blob Viewer — a personal S3/MinIO bucket browser and file previewer by Jason Jiménez Cruz.">
<link rel="icon" href="{base}favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/styles/github-dark.min.css">
<style>
{css}
</style>
</head>
<body>
<div class="layout">
  <aside class="sidenav">
    <a class="brand" href="{base}./"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#4cc2ff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg> Blob Viewer</a>
    <nav>
      {nav}
    </nav>
    <div class="side-foot">
      <a href="https://github.com/jasonjimnz/blob-viewer">GitHub ↗</a>
      <a href="https://pypi.org/project/blob-viewer/">PyPI ↗</a>
    </div>
  </aside>
  <main>
{content}
  </main>
</div>
<script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/highlight.min.js"></script>
<script>hljs.highlightAll();</script>
</body>
</html>
"""

CSS = """
:root { color-scheme: dark; }
* { box-sizing: border-box; margin: 0; }
body { font-family: -apple-system, 'Segoe UI', Roboto, Inter, sans-serif; background: #0f1115; color: #e6eaf2; line-height: 1.65; font-size: 15px; }
.layout { display: grid; grid-template-columns: 250px 1fr; min-height: 100vh; }
.sidenav { background: #12151c; border-right: 1px solid #2a3242; padding: 22px 14px; position: sticky; top: 0; height: 100vh; overflow-y: auto; display: flex; flex-direction: column; }
.brand { display: flex; align-items: center; gap: 9px; font-weight: 700; color: #e6eaf2; text-decoration: none; margin-bottom: 22px; }
.sidenav nav { display: flex; flex-direction: column; gap: 2px; }
.sidenav nav a { color: #8b94a7; text-decoration: none; padding: 7px 10px; border-radius: 8px; font-size: 13.5px; }
.sidenav nav a:hover { background: #232a38; color: #e6eaf2; }
.sidenav nav a.active { background: rgba(76,194,255,.14); color: #4cc2ff; }
.side-foot { margin-top: auto; display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
.side-foot a { color: #5c6577; text-decoration: none; }
.side-foot a:hover { color: #8b94a7; }
main { padding: 40px clamp(20px, 6vw, 80px); max-width: 900px; }
main h1 { font-size: 30px; margin-bottom: 6px; }
main h2 { font-size: 21px; margin: 34px 0 10px; padding-bottom: 6px; border-bottom: 1px solid #2a3242; }
main h3 { font-size: 16.5px; margin: 22px 0 8px; }
main p, main ul, main ol { margin-bottom: 12px; }
main ul, main ol { padding-left: 1.5em; }
main a { color: #4cc2ff; }
main code { background: #141922; border: 1px solid #2a3242; border-radius: 5px; padding: 1px 6px; font-size: 0.88em; font-family: 'Cascadia Code', Consolas, monospace; }
main pre { background: #141922; border: 1px solid #2a3242; border-radius: 10px; padding: 14px 16px; overflow-x: auto; margin-bottom: 14px; }
main pre code { background: none; border: none; padding: 0; }
main table { border-collapse: collapse; margin-bottom: 14px; width: 100%; font-size: 14px; }
main th, main td { border: 1px solid #2a3242; padding: 7px 12px; text-align: left; }
main th { background: #161a22; }
main blockquote { border-left: 3px solid #4cc2ff; padding: 2px 14px; color: #8b94a7; margin-bottom: 12px; }
.footer-note { margin-top: 48px; color: #5c6577; font-size: 12.5px; border-top: 1px solid #2a3242; padding-top: 16px; }
.hero { padding: 8px 0 26px; }
.hero .kicker { color: #4cc2ff; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; font-size: 12px; }
.hero h1 { font-size: clamp(34px, 5vw, 52px); line-height: 1.12; margin: 10px 0 14px; }
.hero .sub { color: #8b94a7; font-size: 18px; max-width: 640px; }
.cta { display: flex; gap: 12px; margin: 26px 0 8px; flex-wrap: wrap; }
.btn { display: inline-block; padding: 11px 20px; border-radius: 10px; font-weight: 600; text-decoration: none; font-size: 14.5px; }
.btn.primary { background: #4cc2ff; color: #06202c; }
.btn.primary:hover { background: #7ad1ff; }
.btn.ghost { border: 1px solid #3a455c; color: #e6eaf2; }
.btn.ghost:hover { border-color: #4cc2ff; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; margin: 30px 0; }
.card { background: #161a22; border: 1px solid #2a3242; border-radius: 12px; padding: 18px; }
.card h3 { margin: 0 0 8px; font-size: 15.5px; color: #4cc2ff; }
.card p { color: #8b94a7; font-size: 13.5px; margin: 0; }
.code-hero { background: #141922; border: 1px solid #2a3242; border-radius: 12px; padding: 18px 20px; font-family: Consolas, monospace; font-size: 13.5px; line-height: 1.8; margin: 22px 0; }
.code-hero .c { color: #5c6577; } .code-hero .g { color: #4ade80; } .code-hero .w { color: #e6eaf2; }
@media (max-width: 860px) { .layout { grid-template-columns: 1fr; } .sidenav { position: static; height: auto; } }
"""


def convert(md_path: pathlib.Path) -> str:
    MD.reset()
    html = MD.convert(md_path.read_text(encoding="utf-8"))
    return html


def page(title: str, content: str, active: str, base: str = "./") -> str:
    nav = "".join(
        f'<a href="{base}{stem}.html" class="{"active" if stem == active else ""}">{label}</a>'
        for stem, label in [(s[:-3], l) for s, l in NAV]
    )
    return PAGE_TMPL.format(title=title, nav=nav, content=content, css=CSS, base=base)


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copy(ROOT / "src/blob_viewer/static/favicon.svg", OUT / "favicon.svg")

    # doc pages
    for stem, _label in [(s[:-3], l) for s, l in NAV]:
        src = DOCS / f"{stem}.md"
        body = convert(src)
        if stem == "index":
            continue
        title = _label
        html = page(title, body + FOOTER, stem)
        (OUT / f"{stem}.html").write_text(html, encoding="utf-8")

    # landing page
    intro = (DOCS / "index.md").read_text(encoding="utf-8")
    landing = LANDING.format(year=datetime.date.today().year)
    (OUT / "index.html").write_text(page("Home", landing, ""), encoding="utf-8")

    print(f"Site built into {OUT}")


FOOTER = """
<div class="footer-note">Blob Viewer — MIT © Jason Jiménez Cruz ·
<a href="https://github.com/jasonjimnz/blob-viewer">github.com/jasonjimnz/blob-viewer</a></div>
"""

LANDING = """
<div class="hero">
  <div class="kicker">Personal · Local-first · S3-compatible</div>
  <h1>Your buckets,<br>finally pleasant to browse.</h1>
  <p class="sub">Blob Viewer connects to any S3-compatible bucket — AWS S3, MinIO, RustFS,
  Backblaze B2, R2, Spaces — or a local folder, and gives you a fast file browser with previews
  for markdown, code, PDFs, images, audio, video and CSV. Every file you open is cached locally:
  your workspace stays available offline, and nothing is ever downloaded twice.</p>
  <div class="cta">
    <a class="btn primary" href="install.html">Get started</a>
    <a class="btn ghost" href="https://github.com/jasonjimnz/blob-viewer">Source on GitHub ↗</a>
  </div>
</div>

<div class="code-hero">
<span class="c"># install & launch the desktop app</span><br>
<span class="g">$</span> <span class="w">pip install blob-viewer</span><br>
<span class="g">$</span> <span class="w">blob-viewer init</span> <span class="c"># guided setup</span><br>
<span class="g">$</span> <span class="w">blob-viewer run</span><br>
<span class="c"># or headless / docker</span><br>
<span class="g">$</span> <span class="w">docker run -d -p 8585:8585 -v bvd:/data ghcr.io/jasonjimnz/blob-viewer:latest</span>
</div>

<div class="cards">
  <div class="card"><h3>Universal previews</h3><p>Markdown, 40+ code languages with syntax
  highlighting, PDFs, images, audio, video, CSV tables — rendered in-app with a sanitising pipeline.</p></div>
  <div class="card"><h3>Smart local cache</h3><p>Files are downloaded once and indexed by ETag.
  When something changes upstream you get an “update” badge and one-click sync — never stale, never re-downloaded.</p></div>
  <div class="card"><h3>Many workspaces</h3><p>Register as many S3 buckets or local folders as you
  want. Remote workspaces are read-only by design; local ones stay fully writable.</p></div>
  <div class="card"><h3>Secrets stay secret</h3><p>Credentials are Fernet-encrypted at rest and
  redacted in the UI and API. Optional locked mode adds a master-admin login for network exposure.</p></div>
  <div class="card"><h3>Air-gap friendly</h3><p>The frontend is vanilla JS/CSS with vendored
  libraries — no CDN, no build step, no telemetry. Perfect for isolated environments.</p></div>
  <div class="card"><h3>Eight themes</h3><p>Dark and light palettes from Obsidian to Nord to Sepia,
  switchable live. Add your own with a few lines of CSS.</p></div>
</div>

<p><a class="btn ghost" href="getting-started.html">Read the docs →</a></p>
"""

if __name__ == "__main__":
    main()
