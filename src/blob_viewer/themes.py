"""Theme registry — single source of truth for the CLI and the UI.

The actual colours live in ``static/css/themes.css`` as ``[data-theme="<name>"]``
blocks; this registry carries the metadata (mode, accent, description) so the
CLI and the settings screen can list and validate them without parsing CSS.
Add a new theme by adding a CSS block and an entry here.
"""

from __future__ import annotations

THEMES: dict[str, dict[str, str]] = {
    # dark
    "obsidian":  {"mode": "dark",  "accent": "cyan",    "description": "Default dark theme, calm and neutral"},
    "midnight":  {"mode": "dark",  "accent": "blue",    "description": "Deep navy blues, OLED friendly"},
    "nord":      {"mode": "dark",  "accent": "frost",   "description": "Nord-inspired arctic palette"},
    "forest":    {"mode": "dark",  "accent": "green",   "description": "Dark greens, easy on the eyes"},
    "aurora":    {"mode": "dark",  "accent": "violet",  "description": "Dark violet with neon accents"},
    # light
    "paper":     {"mode": "light", "accent": "blue",    "description": "Clean white like a modern cloud console"},
    "sepia":     {"mode": "light", "accent": "amber",   "description": "Warm cream tones, reading friendly"},
    "porcelain": {"mode": "light", "accent": "teal",    "description": "Cool light greys with teal accents"},
}

DEFAULT_THEME = "obsidian"

DARK_THEMES = [name for name, t in THEMES.items() if t["mode"] == "dark"]
LIGHT_THEMES = [name for name, t in THEMES.items() if t["mode"] == "light"]


def is_valid_theme(name: str | None) -> bool:
    return name in THEMES
