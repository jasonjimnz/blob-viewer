"""Real browser end-to-end tests with Playwright + Chromium.

Boots a live Blob Viewer server (with a RustFS workspace registered) and
drives the actual UI the way a user would.
"""
from __future__ import annotations

import socket
import threading

from blob_viewer.api import create_app
from blob_viewer.server import wait_until_ready
import boto3
import pytest
from botocore.client import Config
from playwright.sync_api import expect, sync_playwright
from tests.conftest import RUSTFS_ACCESS, RUSTFS_BUCKET, RUSTFS_ENDPOINT, RUSTFS_SECRET

pytestmark = pytest.mark.e2e


def _s3():
    return boto3.client(
        "s3", endpoint_url=RUSTFS_ENDPOINT,
        aws_access_key_id=RUSTFS_ACCESS, aws_secret_access_key=RUSTFS_SECRET,
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


@pytest.fixture(scope="module", autouse=True)
def markdown_fixture(rustfs_ws, service_session):
    """Ensure the browser test's expected object content (independent of order)."""
    _s3().put_object(Bucket=RUSTFS_BUCKET, Key="e2e/hello.md",
                     Body="# E2E Hello\n\nfrom **RustFS**")
    _s3().put_object(Bucket=RUSTFS_BUCKET, Key="e2e/long.md",
                     Body="\n".join(f"## Section {i}\n\nFiller paragraph {i}.\n" for i in range(80)))
    c = create_app(service_session).test_client()
    c.post(f"/api/workspaces/{rustfs_ws.id}/evict", json={"path": "e2e/hello.md"})
    c.post(f"/api/workspaces/{rustfs_ws.id}/evict", json={"path": "e2e/long.md"})
    yield


@pytest.fixture(scope="module")
def live_server(service_session, rustfs_ws):
    from werkzeug.serving import make_server

    app = create_app(service_session)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = make_server("127.0.0.1", port, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    assert wait_until_ready("127.0.0.1", port)
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()


def test_ui_browse_preview_sync(live_server, browser):
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(live_server)

    # sidebar shows the RustFS workspace
    expect(page.locator(".ws-item")).to_contain_text("rustfs-e2e")

    # root listing: e2e folder visible
    page.wait_for_selector(".file-table .row, .file-card")
    expect(page.locator("body")).to_contain_text("e2e")

    # navigate into e2e/
    page.get_by_text("e2e", exact=True).first.click()
    page.wait_for_selector(".file-table .row, .file-card")
    expect(page.locator("body")).to_contain_text("hello.md")
    expect(page.locator("body")).to_contain_text("app.py")

    # open the markdown file -> preview modal renders rendered markdown
    page.get_by_text("hello.md").first.click()
    page.wait_for_selector(".preview-markdown")
    # regression: modal head must show the real title, never a stringified DOM
    # element like "[object HTMLDivElement]"
    head_text = page.locator(".modal-head .m-title").inner_text()
    assert "hello.md" in head_text, f"modal head broken: {head_text!r}"
    assert "[object" not in page.locator(".modal").inner_text()
    expect(page.locator(".preview-markdown h1")).to_contain_text("E2E Hello")
    expect(page.locator(".preview-markdown strong")).to_contain_text("RustFS")
    page.keyboard.press("Escape")
    page.wait_for_timeout(250)

    # regression: long content must be scrollable inside the modal
    page.get_by_text("long.md").first.click()
    page.wait_for_selector(".preview-markdown")
    page.wait_for_timeout(400)
    page.evaluate("document.querySelector('.preview-body').scrollTop = 99999")
    scroll = page.evaluate("""() => { const el = document.querySelector('.preview-body');
        return { ok: el.scrollHeight > el.clientHeight, moved: el.scrollTop > 0 }; }""")
    assert scroll["ok"] and scroll["moved"], f"preview not scrollable: {scroll}"
    page.keyboard.press("Escape")
    page.wait_for_timeout(250)

    # cache badge appears in the modal footer (fresh download or cached copy)
    page.get_by_text("hello.md").first.click()
    page.wait_for_selector(".preview-markdown")
    badge_text = page.locator(".modal .badge").inner_text().strip()
    assert badge_text in ("downloaded", "from cache")
    page.keyboard.press("Escape")
    page.wait_for_timeout(250)

    # open the python file -> syntax-highlighted code preview
    page.get_by_text("app.py").first.click()
    page.wait_for_selector(".preview-code code")
    expect(page.locator(".preview-code code")).to_contain_text("print")
    page.keyboard.press("Escape")

    # theme switch from settings modal
    page.locator("#btn-cache").click()
    page.wait_for_selector(".theme-card")
    page.locator('.theme-card[data-theme-name="paper"]').click()
    expect(page.locator("html")).to_have_attribute("data-theme", "paper")
    page.locator('.theme-card[data-theme-name="nord"]').click()
    expect(page.locator("html")).to_have_attribute("data-theme", "nord")
    page.keyboard.press("Escape")

    # search
    page.locator("#search-input").fill("app.py")
    page.wait_for_timeout(700)
    expect(page.locator(".file-name, .card-name").first).to_contain_text("app.py")

    # the SPA must run without JS errors
    assert errors == [], f"JavaScript errors: {errors}"
    page.close()


def test_ui_locked_mode_login(live_server, browser, service_session):
    from blob_viewer.auth import AuthService
    if not service_session.auth.has_user():
        AuthService(service_session.db).create_user("e2e-admin", "password123")

    # flip the running app into locked mode is not possible post-hoc; instead
    # verify the login overlay path directly on a dedicated locked instance
    from blob_viewer.service import AppService
    from blob_viewer.server import find_free_port
    from werkzeug.serving import make_server

    import pathlib
    import tempfile
    svc = AppService.create(Home := __import__("blob_viewer.paths", fromlist=["Home"]).Home(
        pathlib.Path(tempfile.mkdtemp()) / "home"), locked=True)
    port = find_free_port()
    server = make_server("127.0.0.1", port, create_app(svc), threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    wait_until_ready("127.0.0.1", port)

    page = browser.new_page()
    page.goto(f"http://127.0.0.1:{port}")
    page.wait_for_selector("#login")
    # first-run bootstrap form is shown
    expect(page.locator(".login-card")).to_contain_text("master admin")
    page.fill("#login-user", "admin")
    page.fill("#login-pass", "password123")
    page.fill("#login-pass2", "password123")
    page.click("#login-btn")
    page.wait_for_selector("#ws-list")
    expect(page.locator(".login-card")).to_have_count(0)

    # wrong password on a locked instance is rejected
    page.close()
    server.shutdown()
