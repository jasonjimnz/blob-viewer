"""Server lifecycle: create the Flask app and run it on a real HTTP server.

Two run modes:

* **serve** (headless): production-grade waitress server, bind any host/port.
* **desktop**: binds to ``127.0.0.1`` on an ephemeral port and is opened inside
  a pywebview window (see :mod:`blob_viewer.desktop`).
"""

from __future__ import annotations

import logging
import socket
import sys
import time
from typing import Any

from . import __version__
from .api import create_app
from .service import AppService

log = logging.getLogger("blob-viewer.server")

DEFAULT_PORT = 8585


def find_free_port(host: str = "127.0.0.1", preferred: int | None = None) -> int:
    """Return an available TCP port, preferring *preferred* when free."""
    candidates = ([preferred] if preferred else []) + [0]
    for port in candidates:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port or 0))
            except OSError:
                continue
            return sock.getsockname()[1]
    raise RuntimeError("No free port found")


def build_app(service: AppService) -> Any:
    return create_app(service)


def wait_until_ready(host: str, port: int, timeout: float = 15.0) -> bool:
    """Wait until the server accepts TCP connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.05)
    return False


def run_server(
    service: AppService,
    *,
    host: str = "127.0.0.1",
    port: int | None = None,
    dev: bool = False,
) -> tuple[Any, int]:
    """Start the HTTP server (blocking).  Returns (server, port)."""
    port = port or (DEFAULT_PORT if host != "127.0.0.1" else find_free_port(preferred=DEFAULT_PORT))
    app = build_app(service)
    if dev:
        # werkzeug dev server: only for development and quick desktop use
        from werkzeug.serving import make_server

        server = make_server(host, port, app, threaded=True)
    else:
        from waitress import create_server

        server = create_server(app, host=host, port=port, threads=8)
    _print_banner(host, port, service)
    server.run()
    return server, port


def _print_banner(host: str, port: int, service: AppService) -> None:
    display = "127.0.0.1" if host in ("0.0.0.0", "") else host
    url = f"http://{display}:{port}"
    print(f"\n  Blob Viewer v{__version__}")
    print(f"  Serving on {url}  (data: {service.home.root})")
    if service.locked:
        print("  Locked mode is ON - login required")
    if host in ("0.0.0.0", ""):
        print("  Listening on all interfaces - protected by locked mode only if enabled")
        if not service.locked:
            print("  WARNING: without --locked anyone on your network can read your workspaces")
    print()
    sys.stdout.flush()
