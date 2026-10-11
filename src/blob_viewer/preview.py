"""File type detection for previews.

Blob Viewer renders many file types directly in the UI: markdown, source code
with syntax highlighting, PDFs, images, audio, video, CSV tables and plain
text.  Everything else is offered as a download.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

# categories the frontend can render
CATEGORY_MARKDOWN = "markdown"
CATEGORY_CODE = "code"
CATEGORY_PDF = "pdf"
CATEGORY_IMAGE = "image"
CATEGORY_AUDIO = "audio"
CATEGORY_VIDEO = "video"
CATEGORY_CSV = "csv"
CATEGORY_TEXT = "text"
CATEGORY_BINARY = "binary"

TEXT_EXTENSIONS = {
    ".txt", ".log", ".ini", ".cfg", ".conf", ".toml", ".yaml", ".yml", ".json",
    ".xml", ".sql", ".env", ".properties", ".gitignore", ".editorconfig", ".rst",
    ".adoc", ".tex", ".bib", ".csv", ".tsv", ".htaccess", ".dockerfile",
}

CODE_EXTENSIONS = {
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".java", ".kt", ".kts",
    ".c", ".h", ".cpp", ".hpp", ".cc", ".cs", ".go", ".rs", ".rb", ".php",
    ".swift", ".m", ".mm", ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat",
    ".cmd", ".lua", ".pl", ".pm", ".r", ".jl", ".dart", ".scala", ".clj",
    ".ex", ".exs", ".erl", ".hs", ".elm", ".vue", ".svelte", ".astro", ".css",
    ".scss", ".sass", ".less", ".html", ".htm", ".twig", ".ejs", ".hbs",
    ".groovy", ".gradle", ".cmake", ".make", ".mk", ".dockerfile", ".tf",
    ".hcl", ".proto", ".graphql", ".gql", ".vim", ".asm", ".nasm", ".f90",
    ".pas", ".vb", ".sol", ".zig", ".nim", ".cr", ".d", ".jl",
}

MARKDOWN_EXTENSIONS = {".md", ".markdown", ".mdown", ".mkd", ".mdx"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico", ".avif", ".tiff"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".opus", ".wma"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v", ".ogv"}
PDF_EXTENSIONS = {".pdf"}
CSV_EXTENSIONS = {".csv", ".tsv"}

_HLJS_LANGUAGE = {
    ".py": "python", ".js": "javascript", ".mjs": "javascript", ".ts": "typescript",
    ".java": "java", ".c": "c", ".h": "c", ".cpp": "cpp", ".cs": "csharp",
    ".go": "go", ".rs": "rust", ".rb": "ruby", ".php": "php", ".swift": "swift",
    ".sh": "bash", ".bash": "bash", ".sql": "sql", ".css": "css", ".html": "xml",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "ini", ".xml": "xml",
    ".md": "markdown", ".dockerfile": "dockerfile", ".tf": "hcl", ".kt": "kotlin",
    ".lua": "lua", ".pl": "perl", ".r": "r", ".dart": "dart", ".scala": "scala",
    ".graphql": "graphql", ".proto": "protobuf",
}


def category_for(filename: str, mime: str | None = None) -> str:
    """Classify *filename* into a preview category."""
    suffix = Path(filename).suffix.lower()
    name = Path(filename).name.lower()
    if name == "dockerfile" or suffix == ".dockerfile":
        return CATEGORY_CODE
    if suffix in MARKDOWN_EXTENSIONS:
        return CATEGORY_MARKDOWN
    if suffix in PDF_EXTENSIONS or mime == "application/pdf":
        return CATEGORY_PDF
    if suffix in IMAGE_EXTENSIONS or (mime and mime.startswith("image/")):
        return CATEGORY_IMAGE
    if suffix in AUDIO_EXTENSIONS or (mime and mime.startswith("audio/")):
        return CATEGORY_AUDIO
    if suffix in VIDEO_EXTENSIONS or (mime and mime.startswith("video/")):
        return CATEGORY_VIDEO
    if suffix in CSV_EXTENSIONS:
        return CATEGORY_CSV
    if suffix in CODE_EXTENSIONS:
        return CATEGORY_CODE
    if suffix in TEXT_EXTENSIONS or mime and (mime.startswith("text/") or mime in
            ("application/json", "application/xml", "application/yaml", "application/javascript")):
        return CATEGORY_TEXT
    guessed = mimetypes.guess_type(filename)[0]
    if guessed and (guessed.startswith("text/") or guessed in
            ("application/json", "application/xml", "application/javascript")):
        return CATEGORY_TEXT
    return CATEGORY_BINARY


def mime_for(filename: str) -> str:
    """Best-effort MIME type for serving a file."""
    name = Path(filename).name.lower()
    if name == "dockerfile":
        return "text/x-dockerfile"
    guessed = mimetypes.guess_type(filename)[0]
    if guessed:
        return guessed
    suffix = Path(filename).suffix.lower()
    if suffix in TEXT_EXTENSIONS or suffix in CODE_EXTENSIONS or suffix in MARKDOWN_EXTENSIONS:
        return "text/plain"
    return "application/octet-stream"


def hljs_language(filename: str) -> str | None:
    return _HLJS_LANGUAGE.get(Path(filename).suffix.lower())
