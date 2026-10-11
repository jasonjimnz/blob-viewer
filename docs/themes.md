# Themes & customisation

Blob Viewer ships with eight themes, switchable live from **Settings → Appearance** (or `blob-viewer theme set <name>`). Your choice is stored server-side and applied instantly.

| Name | Mode | Accent | Vibe |
|---|---|---|---|
| `obsidian` | dark | cyan | default — calm, neutral dark |
| `midnight` | dark | blue | deep navy, OLED friendly |
| `nord` | dark | frost | Nord-inspired arctic palette |
| `forest` | dark | green | dark greens, easy on the eyes |
| `aurora` | dark | violet | dark violet with neon accents |
| `paper` | light | blue | clean cloud-console white |
| `sepia` | light | amber | warm cream, reading friendly |
| `porcelain` | light | teal | cool light greys, teal accents |

## Adding your own theme

1. Add a `[data-theme="mytheme"]` block to `src/blob_viewer/static/css/themes.css` defining the CSS custom properties (copy an existing block as a starting point):

```css
[data-theme="mytheme"] {
  --bg: #101418;  --bg-alt: #171d24;  /* …all variables from an existing theme… */
  --accent: #ff7a59;  --accent-contrast: #1a0e08;
  color-scheme: dark;
}
```

2. Register it in `src/blob_viewer/themes.py`:

```python
"mytheme": {"mode": "dark", "accent": "orange", "description": "My custom theme"},
```

3. Restart. The theme appears in the CLI, the settings grid and validation automatically.

## Customising without forking

The UI is dependency-free vanilla HTML/JS/CSS served from `src/blob_viewer/static/`. You can freely edit those files in an editable install (`pip install -e .`) — they are static assets, no build step. `templates/index.html` wires everything; `static/js/app.js` is the whole application.

The layout is keyboard- and mobile-friendly: Escape closes modals, `Enter` submits the login form, and below 860px the sidebar collapses to icons.
