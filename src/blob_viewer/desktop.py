"""Desktop application shell (pywebview).

Starts the Flask server on a loopback port and opens it in a native window.
With ``--locked`` the user must sign in inside the window before anything is
accessible.
"""

from __future__ import annotations

import logging
import threading

from . import __version__
from .auth import AuthError
from .server import find_free_port, wait_until_ready
from .service import AppService

log = logging.getLogger("blob-viewer.desktop")


def run_desktop(service: AppService, *, port: int | None = None) -> None:
    """Open Blob Viewer in a native pywebview window (blocking)."""
    try:
        import webview
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "pywebview is required for desktop mode. Install it with "
            "'pip install blob-viewer[desktop]' or use 'blob-viewer serve'."
        ) from exc

    host = "127.0.0.1"
    port = port or find_free_port(host)
    app_module = _start_server_thread(service, host, port)
    if not wait_until_ready(host, port):
        raise RuntimeError("The internal server did not start")

    url = f"http://{host}:{port}/"
    print(f"  Opening Blob Viewer v{__version__} at {url}")

    window = webview.create_window(
        "Blob Viewer",
        url=url,
        width=1360,
        height=880,
        min_size=(900, 600),
        background_color="#0f1115",
    )

    def _on_shown() -> None:
        log.debug("window shown")

    webview.start(func=_on_shown, debug=False)
    log.debug("window closed, stopping server")
    if app_module is not None:
        try:
            app_module.shutdown()
        except Exception:  # noqa: BLE001 - best effort shutdown
            pass


def _start_server_thread(service: AppService, host: str, port: int):
    from werkzeug.serving import make_server

    from .api import create_app

    server = make_server(host, port, create_app(service), threaded=True)
    thread = threading.Thread(target=server.serve_forever, name="blob-viewer-server", daemon=True)
    thread.start()
    return server


def ensure_locked_user(service: AppService, *, prompt) -> None:
    """Interactive bootstrap of the master admin for locked mode.

    *prompt* is a callable(headline, password=False) -> str (e.g. rich.prompt).
    """
    if service.auth.has_user():
        return
    print("\n  Locked mode is enabled but no master admin exists yet.")
    print("  Create the administrator account that will unlock the app.\n")
    while True:
        username = prompt("Master admin username", default="admin")
        password = prompt("Master admin password", password=True)
        confirm = prompt("Confirm password", password=True)
        try:
            if password != confirm:
                raise AuthError("Passwords do not match")
            service.auth.create_user(username, password)
            print(f"\n  Master admin '{username}' created.\n")
            return
        except AuthError as exc:
            print(f"  ! {exc}")
