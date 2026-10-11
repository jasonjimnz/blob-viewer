"""Application service container.

:class:`AppService` wires the home directory, database, secret store, workspace
store, auth service and cache manager into one object shared by the Flask app,
the CLI and the desktop launcher.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from . import __version__
from .auth import AuthService
from .cache import CacheManager
from .db import Database
from .paths import Home
from .secrets import SecretStore
from .workspaces import WorkspaceStore

# user-changeable settings and their defaults
DEFAULT_SETTINGS: dict[str, str] = {
    "theme": "obsidian",
    "view_mode": "list",        # 'list' | 'grid'
    "sort_by": "name",          # 'name' | 'size' | 'modified'
    "sort_dir": "asc",
    "show_hidden": "0",
    "confirm_delete": "1",
}


@dataclass
class AppService:
    home: Home
    db: Database
    secrets: SecretStore
    workspaces: WorkspaceStore
    auth: AuthService
    cache: CacheManager
    locked: bool = False
    settings_cache: dict = field(default_factory=dict, init=False, repr=False)

    @classmethod
    def create(cls, home: Home | None = None, *, locked: bool = False) -> "AppService":
        home = home or Home.from_env()
        home.ensure()
        db = Database(home.db_path)
        db.initialise()
        secrets = SecretStore(home.key_path)
        return cls(
            home=home,
            db=db,
            secrets=secrets,
            workspaces=WorkspaceStore(db, secrets),
            auth=AuthService(db),
            cache=CacheManager(home, db),
            locked=locked,
        )

    # -- settings -----------------------------------------------------------

    def all_settings(self) -> dict[str, str]:
        merged = dict(DEFAULT_SETTINGS)
        for key in list(merged):
            value = self.db.get_setting(f"setting:{key}")
            if value is not None:
                merged[key] = value
        return merged

    def get_setting(self, key: str) -> str:
        if key not in DEFAULT_SETTINGS:
            raise KeyError(f"Unknown setting '{key}'")
        return self.db.get_setting(f"setting:{key}", DEFAULT_SETTINGS[key])

    def update_settings(self, values: dict[str, str]) -> dict[str, str]:
        for key, value in values.items():
            if key not in DEFAULT_SETTINGS:
                raise KeyError(f"Unknown setting '{key}'")
            if not isinstance(value, str):
                raise ValueError(f"Setting '{key}' must be a string")
            self.db.set_setting(f"setting:{key}", value)
        return self.all_settings()

    # -- misc ---------------------------------------------------------------

    def version(self) -> str:
        return __version__

    def data_dir_size(self) -> int:
        total = 0
        for root, _dirs, files in os.walk(self.home.cache_dir):
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(root, name))
                except OSError:
                    pass
        return total
