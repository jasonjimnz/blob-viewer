"""Blob Viewer — a personal S3/MinIO bucket browser and file previewer.

Blob Viewer lets you register many *workspaces* (S3-compatible buckets or local
folders), navigate their contents with a modern web UI (MinIO / OneDrive style),
preview almost any file type and keep a local download cache so files are only
fetched once.
"""

__title__ = "blob-viewer"
__version__ = "0.1.2"
__author__ = "Jason Jiménez Cruz"
__license__ = "MIT"
__app_name__ = "Blob Viewer"
__url__ = "https://github.com/jasonjimnz/blob-viewer"

APP_NAME = __app_name__
APP_USER_AGENT = f"blob-viewer/{__version__}"
