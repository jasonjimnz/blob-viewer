"""Blob Viewer command line interface.

A guided CLI built on ``rich``: ``blob-viewer init`` walks you through first
configuration; every other subcommand supports ``--help``.  Non-interactive
flags are available for scripting (e.g. containers).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table

from . import __app_name__, __version__
from .auth import AuthError
from .paths import Home, HOME_ENV_VAR
from .server import DEFAULT_PORT, run_server
from .service import AppService
from .themes import THEMES
from .storage import StorageError, factory
from .workspaces import REDACTED_SENTINEL, WorkspaceError, WorkspaceNotFound

console = Console(legacy_windows=False)

EPILOG = f"[dim]{__app_name__} v{__version__} — https://github.com/jasonjimnz/blob-viewer[/dim]"


def _make_console_safe() -> None:
    """Guarantee UTF-8 output even on legacy cp1252 Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover
            pass


def _ask(message: str, default: str = "") -> str:
    try:
        return Prompt.ask(message, default=default, console=console).strip()
    except EOFError:  # non-interactive stdin
        return default


def _secret(message: str) -> str:
    try:
        return Prompt.ask(message, password=True, console=console).strip()
    except EOFError:
        return ""


def _confirm(message: str, default: bool = False) -> bool:
    try:
        return Confirm.ask(message, default=default, console=console)
    except EOFError:
        return default


def _ask_with_choices(message: str, choices: list[str], default: str) -> str:
    try:
        return Prompt.ask(message, choices=choices, default=default, console=console)
    except EOFError:
        return default


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _make_console_safe()
    try:
        return args.func(args) or 0
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
        return 130
    except (WorkspaceError, StorageError, AuthError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return 1
    except BrokenPipeError:
        return 0


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="blob-viewer",
        description="A personal S3/MinIO bucket browser and file previewer.",
        epilog=EPILOG,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--home", metavar="DIR", help=f"application data directory (default: ~/{Home('x').root.name} or ${HOME_ENV_VAR})"
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    def add(name: str, help_: str, func) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_, description=help_, epilog=EPILOG)
        sp.set_defaults(func=func)
        sp.add_argument("--home", metavar="DIR", help=argparse.SUPPRESS)
        return sp

    p_init = add("init", "Guided first-run configuration", _cmd_init)
    p_init.add_argument("--locked", action="store_true", help="enable login requirement")

    p_run = add("run", "Launch the desktop app (pywebview window)", _cmd_run)
    p_run.add_argument("--locked", action="store_true", help="require master-admin login")
    p_run.add_argument("--port", type=int, default=None, help="preferred internal port")

    p_serve = add("serve", "Run as a headless HTTP server", _cmd_serve)
    p_serve.add_argument("--locked", action="store_true", help="require master-admin login")
    p_serve.add_argument("--host", default="127.0.0.1", help="bind address (default: 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port (default: {DEFAULT_PORT})")
    p_serve.add_argument("--open", action="store_true", help="open the browser automatically")

    p_ws = add("workspace", "Manage workspaces", _cmd_workspace_noop)
    ws_sub = p_ws.add_subparsers(dest="ws_command", metavar="<action>")

    def ws_cmd(name: str, help_: str, func) -> argparse.ArgumentParser:
        sp = ws_sub.add_parser(name, help=help_, description=help_, epilog=EPILOG)
        sp.set_defaults(func=func)
        return sp

    p_add = ws_cmd("add", "Add a new workspace (guided)", _cmd_ws_add)
    _add_noninteractive_flags(p_add)
    p_edit = ws_cmd("edit", "Edit a workspace", _cmd_ws_edit)
    p_edit.add_argument("name", help="workspace name")
    _add_noninteractive_flags(p_edit)
    p_list = ws_cmd("list", "List configured workspaces", _cmd_ws_list)
    p_list.add_argument("--json", action="store_true", help="machine-readable output")
    p_show = ws_cmd("show", "Show details of one workspace", _cmd_ws_show)
    p_show.add_argument("name", help="workspace name")
    p_test = ws_cmd("test", "Test connectivity of a workspace", _cmd_ws_test)
    p_test.add_argument("name", help="workspace name")
    p_remove = ws_cmd("remove", "Remove a workspace (its cache is kept until purged)", _cmd_ws_remove)
    p_remove.add_argument("name", help="workspace name")
    p_remove.add_argument("-y", "--yes", action="store_true", help="skip confirmation")

    p_user = add("user", "Manage the master admin (locked mode)", _cmd_user_noop)
    user_sub = p_user.add_subparsers(dest="user_command", metavar="<action>")
    p_uc = user_sub.add_parser("create", help="Create the master admin (first run)", epilog=EPILOG)
    p_uc.set_defaults(func=_cmd_user_create)
    p_uc.add_argument("--username", default=None, help="admin username")
    p_uc.add_argument("--password", default=None, help="admin password (careful: shell history)")
    p_ur = user_sub.add_parser("reset", help="Replace the master admin", epilog=EPILOG)
    p_ur.set_defaults(func=_cmd_user_reset)
    p_ur.add_argument("--username", default=None, help="new admin username")
    p_ur.add_argument("--password", default=None, help="new admin password (careful: shell history)")
    p_us = user_sub.add_parser("status", help="Show whether an admin exists", epilog=EPILOG)
    p_us.set_defaults(func=_cmd_user_status)

    p_cache = add("cache", "Inspect and manage the download cache", _cmd_cache_noop)
    cache_sub = p_cache.add_subparsers(dest="cache_command", metavar="<action>")
    p_cs = cache_sub.add_parser("stats", help="Show cache statistics", epilog=EPILOG)
    p_cs.set_defaults(func=_cmd_cache_stats)
    p_cc = cache_sub.add_parser("clear", help="Delete cached files", epilog=EPILOG)
    p_cc.set_defaults(func=_cmd_cache_clear)
    p_cc.add_argument("--workspace", default=None, help="only clear this workspace")
    p_cc.add_argument("-y", "--yes", action="store_true", help="skip confirmation")

    p_theme = add("theme", "Change the UI theme", _cmd_theme_noop)
    theme_sub = p_theme.add_subparsers(dest="theme_command", metavar="<action>")
    p_tl = theme_sub.add_parser("list", help="List available themes", epilog=EPILOG)
    p_tl.set_defaults(func=_cmd_theme_list)
    p_ts = theme_sub.add_parser("set", help="Set the default theme", epilog=EPILOG)
    p_ts.set_defaults(func=_cmd_theme_set)
    p_ts.add_argument("name", help="theme name (see 'theme list')")

    p_doc = add("doctor", "Diagnose installation problems", _cmd_doctor)
    p_ver = add("version", "Show version information", _cmd_version)

    return parser


def _add_noninteractive_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--kind", choices=("s3", "local"), help="workspace kind")
    p.add_argument("--name", help="workspace name")
    p.add_argument("--endpoint", help="S3 endpoint URL")
    p.add_argument("--bucket", help="S3 bucket name")
    p.add_argument("--region", help="S3 region")
    p.add_argument("--prefix", help="root prefix inside the bucket")
    p.add_argument("--path-style", action="store_true", default=None, help="force path-style addressing")
    p.add_argument("--access-key", help="S3 access key")
    p.add_argument("--secret-key", help="S3 secret key (careful: shell history)")
    p.add_argument("--local-path", help="folder for local workspaces")
    p.add_argument("--read-only", action="store_true", help="mark a local workspace read-only")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _service(args) -> AppService:  # noqa: ANN001
    home = Home.from_env(getattr(args, "home", None) or None)
    return AppService.create(home)


def _banner() -> None:
    console.print(
        Panel(
            f"[b]{__app_name__}[/b] v{__version__}\n"
            "[dim]A personal S3/MinIO bucket browser and file previewer[/dim]\n"
            "[dim]by Jason Jiménez Cruz — github.com/jasonjimnz/blob-viewer[/dim]",
            border_style="cyan",
            padding=(0, 2),
        )
    )


def _fmt_size(num: float | int | None) -> str:
    num = float(num or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024:
            return f"{num:,.0f} {unit}" if unit == "B" else f"{num:,.1f} {unit}"
        num /= 1024
    return f"{num:,.1f} PB"


def _workspace_table(service: AppService) -> Table:
    table = Table(title="Workspaces", show_lines=False, border_style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Kind")
    table.add_column("Target")
    table.add_column("Mode")
    table.add_column("Cached", justify="right")
    for ws in service.workspaces.list():
        target = ws.endpoint if ws.kind == "s3" else ws.local_path
        bucket = f"/{ws.bucket}" if ws.bucket else ""
        entries = service.cache.list_entries(ws.id)
        table.add_row(
            ws.name,
            ws.kind,
            f"{target}{bucket}",
            "read-only" if not ws.writable else "writable",
            f"{len(entries)} files",
        )
    return table


def _prompt_s3(prefix_default: str = "") -> dict:
    endpoint = _ask("Endpoint URL", "http://localhost:9000")
    bucket = _ask("Bucket name")
    region = _ask("Region [dim]optional[/dim]")
    prefix = _ask("Root prefix inside the bucket [dim]optional[/dim]", prefix_default)
    console.print("[dim]Credentials are stored encrypted in your Blob Viewer home.[/dim]")
    access_key = _ask("Access key [dim]leave empty for anonymous access[/dim]")
    secret_key = ""
    if access_key:
        secret_key = _secret("Secret key")
    path_style = _confirm("Use path-style addressing? (recommended for MinIO/R2/B2)", True)
    return {
        "endpoint": endpoint,
        "bucket": bucket,
        "region": region or None,
        "prefix": prefix or None,
        "path_style": path_style,
        "secrets": {"access_key": access_key or None, "secret_key": secret_key or None},
    }


def _test_and_report(service: AppService, ws_id: str, *, credentials: dict | None = None) -> bool:
    from .api import json_body  # noqa: F401  (import check only)

    ws = service.workspaces.get(ws_id)
    with console.status("[bold cyan]Testing connection…"):
        try:
            backend = factory.storage_for(ws)
            result = backend.test_connection()
            console.print(f"[green]✓[/green] {result['message']}")
            return True
        except StorageError as exc:
            console.print(f"[red]✗[/red] {exc}")
            console.print("[dim]You can fix the settings later with 'blob-viewer workspace edit'.[/dim]")
            return False


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #


def _cmd_workspace_noop(args) -> int:  # noqa: ANN001
    _build_parser().parse_args(["workspace", "--help"])
    return 0


def _cmd_user_noop(args) -> int:  # noqa: ANN001
    _build_parser().parse_args(["user", "--help"])
    return 0


def _cmd_cache_noop(args) -> int:  # noqa: ANN001
    _build_parser().parse_args(["cache", "--help"])
    return 0


def _cmd_theme_noop(args) -> int:  # noqa: ANN001
    _build_parser().parse_args(["theme", "--help"])
    return 0


def _cmd_init(args) -> int:  # noqa: ANN001
    _banner()
    service = _service(args)
    console.print(f"Data directory: [bold]{service.home.root}[/bold]\n")

    if args.locked and not service.auth.has_user():
        _create_user_interactive(service)

    if service.workspaces.list():
        console.print("[green]You already have workspaces configured.[/green]")
        console.print(_workspace_table(service))
        if not _confirm("Add another workspace?"):
            _print_next_steps(service, locked=args.locked)
            return 0

    if _confirm("Add your first workspace now?", True):
        _cmd_ws_add(args, initial=True)

    _print_next_steps(service, locked=args.locked)
    return 0


def _print_next_steps(service: AppService, *, locked: bool) -> None:  # noqa: ANN001
    console.print(Rule(style="dim"))
    steps = ["[bold]blob-viewer run[/bold]        open the desktop app", "[bold]blob-viewer serve[/bold]      run as a headless server"]
    if locked:
        steps.insert(1, "[bold]blob-viewer run --locked[/bold]  open the desktop app (login required)")
    console.print("Next steps:")
    for step in steps:
        console.print(f"  • {step}")
    console.print(f"  • [bold]blob-viewer workspace add[/bold]  more workspaces ({len(service.workspaces.list())} configured)")


def _cmd_run(args) -> int:  # noqa: ANN001
    service = _service(args)
    if args.locked:
        service.locked = True
        if not service.auth.has_user():
            from .desktop import ensure_locked_user

            _banner()
            ensure_locked_user(service, prompt=_rich_prompt)
        else:
            _banner()
    else:
        _banner()
    try:
        from .desktop import run_desktop

        run_desktop(service, port=args.port)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        console.print("[dim]Falling back to server mode: open the URL above in your browser.[/dim]")
        run_server(service, host="127.0.0.1", port=args.port, dev=True)
    return 0


def _rich_prompt(message: str, *, password: bool = False, default=None):  # noqa: ANN001, ARG001
    if password:
        return Prompt.ask(message, password=True, console=console)
    return Prompt.ask(message, console=console)


def _cmd_serve(args) -> int:  # noqa: ANN001
    service = _service(args)
    if args.locked:
        service.locked = True
        if not service.auth.has_user():
            _banner()
            console.print("[yellow]Locked mode requires a master admin.[/yellow]")
            _create_user_interactive(service)
    if args.open:
        host_display = "127.0.0.1"
        import threading

        threading.Timer(
            1.0, lambda: webbrowser.open(f"http://{host_display}:{args.port}")
        ).start()
    run_server(service, host=args.host, port=args.port)
    return 0


def _create_user_interactive(service: AppService) -> None:  # noqa: ANN001
    console.print("\n[bold]Create the master admin account[/bold] [dim](unlock credentials for locked mode)[/dim]\n")
    while True:
        username = _ask("Username", "admin")
        password = _secret("Password")
        confirm = _secret("Confirm password")
        try:
            if password != confirm:
                raise AuthError("Passwords do not match")
            service.auth.create_user(username, password)
            console.print(f"[green]✓[/green] Master admin '[bold]{username}[/bold]' created\n")
            return
        except AuthError as exc:
            console.print(f"[red]✗[/red] {exc}")


def _cmd_ws_add(args, initial: bool = False) -> int:  # noqa: ANN001
    service = _service(args)
    if not initial:
        _banner()
    interactive = sys.stdin.isatty()
    data: dict = {}
    kind = getattr(args, "kind", None) or (
        _ask_with_choices("Workspace kind", ["s3", "local"], "s3")
        if interactive
        else "s3"
    )
    data["kind"] = kind
    if not data.get("name") and not interactive:
        console.print("[red]Error:[/red] --name is required when running non-interactively")
        return 1
    if kind == "s3":
        data["name"] = args.name or _ask("Workspace name")
        if args.endpoint and args.bucket:
            # fully non-interactive invocation
            data.update(
                endpoint=args.endpoint, bucket=args.bucket, region=args.region,
                prefix=args.prefix,
                path_style=bool(args.path_style) or (interactive and _confirm("Use path-style addressing?", True)),
            )
            secrets: dict[str, str | None] = {}
            if args.access_key:
                secrets["access_key"] = args.access_key
            if args.secret_key:
                secrets["secret_key"] = args.secret_key
            if secrets:
                data["secrets"] = secrets
        else:
            if not interactive:
                console.print("[red]Error:[/red] --endpoint and --bucket are required when running non-interactively")
                return 1
            s3 = _prompt_s3()
            data.update({k: v for k, v in s3.items() if v not in (None, "", {})})
        if args.access_key:
            data.setdefault("secrets", {})["access_key"] = args.access_key
        if args.secret_key:
            data.setdefault("secrets", {})["secret_key"] = args.secret_key
    else:
        data["name"] = args.name or _ask("Workspace name")
        data["local_path"] = args.local_path or _ask("Folder path")
        read_only = args.read_only or _confirm("Make it read-only?")
        if read_only:
            data["read_only"] = True

    try:
        ws = service.workspaces.create(data)
        console.print(f"\n[green]✓[/green] Workspace '[bold]{ws.name}[/bold]' created (id {ws.id[:8]}…)")
    except WorkspaceError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return 1
    _test_and_report(service, ws.id)
    return 0


def _cmd_ws_edit(args) -> int:  # noqa: ANN001
    service = _service(args)
    try:
        ws = service.workspaces.get_by_name(args.name)
    except WorkspaceError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return 1
    if ws is None:
        console.print(f"[red]Error:[/red] no workspace named '{args.name}'")
        return 1
    console.print(f"Editing [bold]{ws.name}[/bold]. Press Enter to keep the current value.")
    updates: dict = {}
    if ws.kind == "s3":
        updates["endpoint"] = _ask("Endpoint URL", ws.endpoint or "") or ws.endpoint
        updates["bucket"] = _ask("Bucket", ws.bucket or "") or ws.bucket
        updates["region"] = _ask("Region", ws.region or "") or None
        updates["prefix"] = _ask("Prefix", ws.prefix or "") or None
        if _confirm("Change credentials?"):
            updates["secrets"] = _prompt_s3()["secrets"]
    else:
        updates["local_path"] = _ask("Folder path", ws.local_path or "") or ws.local_path
        updates["read_only"] = _confirm("Read-only?", ws.read_only)
    service.workspaces.update(ws.id, updates)
    console.print("[green]✓[/green] Workspace updated")
    return 0


def _cmd_ws_list(args) -> int:  # noqa: ANN001
    service = _service(args)
    workspaces = service.workspaces.list()
    if args.json:
        print(json.dumps([ws.to_api() for ws in workspaces], indent=2))
        return 0
    if not workspaces:
        console.print("No workspaces yet. Add one with [bold]blob-viewer workspace add[/bold].")
        return 0
    console.print(_workspace_table(service))
    return 0


def _cmd_ws_show(args) -> int:  # noqa: ANN001
    service = _service(args)
    ws = service.workspaces.get_by_name(args.name)
    if ws is None:
        console.print(f"[red]Error:[/red] no workspace named '{args.name}'")
        return 1
    api = ws.to_api()
    table = Table(show_header=False, border_style="dim", title=ws.name)
    table.add_column(style="bold")
    table.add_column()
    rows = [
        ("id", api["id"]), ("kind", api["kind"]), ("endpoint", api["endpoint"]),
        ("bucket", api["bucket"]), ("region", api["region"]), ("prefix", api["prefix"]),
        ("path_style", api["path_style"]), ("local_path", api["local_path"]),
        ("read_only", api["read_only"]), ("writable", api["writable"]),
        ("description", api["description"]),
        ("access_key", api["secrets"]["access_key"] or "[dim]not set[/dim]"),
        ("secret_key", api["secrets"]["secret_key"] or "[dim]not set[/dim]"),
    ]
    for key, value in rows:
        table.add_row(key, str(value))
    console.print(table)
    cached = service.cache.list_entries(ws.id)
    console.print(f"\n[dim]{len(cached)} files in the local cache ({_fmt_size(sum(e.size or 0 for e in cached))})[/dim]")
    return 0


def _cmd_ws_test(args) -> int:  # noqa: ANN001
    service = _service(args)
    ws = service.workspaces.get_by_name(args.name)
    if ws is None:
        console.print(f"[red]Error:[/red] no workspace named '{args.name}'")
        return 1
    ok = _test_and_report(service, ws.id)
    return 0 if ok else 1


def _cmd_ws_remove(args) -> int:  # noqa: ANN001
    service = _service(args)
    ws = service.workspaces.get_by_name(args.name)
    if ws is None:
        console.print(f"[red]Error:[/red] no workspace named '{args.name}'")
        return 1
    if not args.yes and not _confirm(
        f"Remove workspace '[bold]{ws.name}[/bold]'? Cached files are purged too."
    ):
        console.print("Cancelled.")
        return 0
    service.workspaces.delete(ws.id)
    removed = service.cache.clear(ws.id)
    console.print(f"[green]✓[/green] Removed '{ws.name}' and {removed} cached files")
    return 0


def _cmd_user_create(args) -> int:  # noqa: ANN001
    service = _service(args)
    if service.auth.has_user():
        console.print("[yellow]A master admin already exists.[/yellow] Use [bold]blob-viewer user reset[/bold] to replace it.")
        return 1
    if args.username and args.password:
        service.auth.create_user(args.username, args.password)
    else:
        _create_user_interactive(service)
    console.print("[green]✓[/green] Master admin created. Start the app with [bold]--locked[/bold] to require login.")
    return 0


def _cmd_user_reset(args) -> int:  # noqa: ANN001
    service = _service(args)
    if args.username and args.password:
        service.auth.reset_user(args.username, args.password)
        console.print(f"[green]✓[/green] Master admin replaced with '[bold]{args.username}[/bold]'. All sessions were revoked.")
        return 0
    console.print("[bold]Replacing the master admin.[/bold] All existing sessions will be revoked.\n")
    while True:
        username = _ask("New username", "admin")
        password = _secret("New password")
        confirm = _secret("Confirm password")
        if password != confirm:
            console.print("[red]✗[/red] Passwords do not match")
            continue
        service.auth.reset_user(username, password)
        console.print(f"[green]✓[/green] Master admin replaced with '[bold]{username}[/bold]'.")
        return 0


def _cmd_user_status(args) -> int:  # noqa: ANN001
    service = _service(args)
    if service.auth.has_user():
        console.print(f"Master admin configured: [bold]{service.auth.username()}[/bold]")
    else:
        console.print("No master admin configured. Locked mode will ask you to create one on first run.")
    return 0


def _cmd_cache_stats(args) -> int:  # noqa: ANN001
    service = _service(args)
    stats = service.cache.stats()
    console.print(f"Home directory: [bold]{service.home.root}[/bold]")
    console.print(f"Cached files:   [bold]{stats['files']}[/bold] ({_fmt_size(stats['bytes'])} on disk)")
    table = Table(border_style="dim")
    table.add_column("Workspace")
    table.add_column("Files", justify="right")
    table.add_column("Size", justify="right")
    for ws in service.workspaces.list():
        entries = service.cache.list_entries(ws.id)
        if entries:
            table.add_row(ws.name, str(len(entries)), _fmt_size(sum(e.size or 0 for e in entries)))
    if table.row_count:
        console.print(table)
    return 0


def _cmd_cache_clear(args) -> int:  # noqa: ANN001
    service = _service(args)
    workspace_id = None
    if args.workspace:
        ws = service.workspaces.get_by_name(args.workspace)
        if ws is None:
            console.print(f"[red]Error:[/red] no workspace named '{args.workspace}'")
            return 1
        workspace_id = ws.id
    if not args.yes:
        scope = f"workspace '{args.workspace}'" if workspace_id else "ALL workspaces"
        if not _confirm(f"Delete all cached files for {scope}?"):
            console.print("Cancelled.")
            return 0
    removed = service.cache.clear(workspace_id)
    console.print(f"[green]✓[/green] Removed {removed} cached files")
    return 0


def _cmd_theme_list(args) -> int:  # noqa: ANN001
    service = _service(args)
    current = service.get_setting("theme")
    table = Table(title="Themes", border_style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Mode")
    table.add_column("Accent")
    table.add_column()
    for name, theme in THEMES.items():
        marker = "[green]← current[/green]" if name == current else ""
        table.add_row(name, theme["mode"], theme["accent"], marker)
    console.print(table)
    console.print("[dim]Preview themes live in the UI (Settings → Appearance).[/dim]")
    return 0


def _cmd_theme_set(args) -> int:  # noqa: ANN001
    service = _service(args)
    if args.name not in THEMES:
        console.print(f"[red]Error:[/red] unknown theme '{args.name}'. Available: {', '.join(THEMES)}")
        return 1
    service.update_settings({"theme": args.name})
    console.print(f"[green]✓[/green] Default theme set to '[bold]{args.name}[/bold]'")
    return 0


def _cmd_doctor(args) -> int:  # noqa: ANN001
    _banner()
    service = _service(args)
    checks: list[tuple[str, bool, str]] = []

    checks.append(("Python version", sys.version_info >= (3, 11), sys.version.split()[0]))
    try:
        import boto3  # noqa: F401
        checks.append(("boto3 (S3 support)", True, boto3.__version__))
    except ImportError:  # pragma: no cover
        checks.append(("boto3 (S3 support)", False, "missing"))
    try:
        import webview  # noqa: F401
        checks.append(("pywebview (desktop window)", True, getattr(webview, "__version__", "?")))
    except ImportError:
        checks.append(("pywebview (desktop window)", False, "missing — 'serve' mode still works"))
    try:
        from cryptography.fernet import Fernet  # noqa: F401
        checks.append(("cryptography (secret encryption)", True, "ok"))
    except ImportError:  # pragma: no cover
        checks.append(("cryptography (secret encryption)", False, "missing"))
    try:
        from waitress import create_server  # noqa: F401
        checks.append(("waitress (production server)", True, "ok"))
    except ImportError:  # pragma: no cover
        checks.append(("waitress (production server)", False, "missing"))
    checks.append(("Data directory writable", os.access(service.home.root, os.W_OK), str(service.home.root)))
    checks.append(("Secrets key present", service.home.key_path.exists(), str(service.home.key_path)))
    checks.append(("Database present", service.home.db_path.exists(), str(service.home.db_path)))

    table = Table(title="Doctor", border_style="dim")
    table.add_column("Check")
    table.add_column("Status", justify="center")
    table.add_column("Detail")
    failed = 0
    for name, ok, detail in checks:
        if not ok:
            failed += 1
        table.add_row(name, "[green]✓[/green]" if ok else "[red]✗[/red]", detail)
    console.print(table)
    console.print(f"\nWorkspaces configured: {len(service.workspaces.list())}")
    if service.auth.has_user():
        console.print("Locked mode ready: master admin exists")
    else:
        console.print("[dim]Locked mode not configured (optional).[/dim]")
    return 1 if failed else 0


def _cmd_version(args) -> int:  # noqa: ANN001, ARG001
    console.print(f"{__app_name__} v{__version__}")
    console.print(f"[dim]Python {sys.version.split()[0]} — https://github.com/jasonjimnz/blob-viewer[/dim]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
