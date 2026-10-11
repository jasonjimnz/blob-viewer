"""Authentication for locked mode.

Blob Viewer is open by default — it is a personal tool and normally binds to
``127.0.0.1`` only.  When the user starts it with the ``--locked`` flag, a
master admin account must exist (created interactively on first run) and every
API request — desktop and browser alike — requires login.

Passwords use PBKDF2-HMAC-SHA256 (210,000 iterations) from the standard
library; sessions are opaque random tokens stored server-side with an expiry.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets as _secrets

from .db import Database, new_id, now
from .secrets import SecretStore

PBKDF2_ITERATIONS = 210_000
SESSION_TTL_SECONDS = 12 * 60 * 60  # 12 hours


class AuthError(Exception):
    pass


class AuthService:
    def __init__(self, db: Database) -> None:
        self.db = db

    # -- users ----------------------------------------------------------------

    def has_user(self) -> bool:
        return self.db.query_one("SELECT 1 FROM users LIMIT 1") is not None

    def create_user(self, username: str, password: str, *, force: bool = False) -> None:
        username = (username or "").strip()
        if not username:
            raise AuthError("Username is required")
        if len(password) < 8:
            raise AuthError("Password must be at least 8 characters")
        if self.has_user() and not force:
            raise AuthError("A master admin already exists. Use 'user reset' to change it.")
        salt = _secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
        encoded = f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"
        with self.db.connect() as conn:
            conn.execute("DELETE FROM users")
            conn.execute(
                "INSERT INTO users (id, username, password_hash, created_at) VALUES (?,?,?,?)",
                (new_id(), username, encoded, now()),
            )
            conn.execute("DELETE FROM auth_sessions")  # invalidate old sessions

    def reset_user(self, username: str, password: str) -> None:
        """Replace the master admin (requires physical access / CLI)."""
        self.create_user(username, password, force=True)

    def verify_credentials(self, username: str, password: str) -> bool:
        row = self.db.query_one(
            "SELECT password_hash FROM users WHERE username = ?", ((username or "").strip(),)
        )
        if row is None:
            # constant-time-ish dummy check to avoid user enumeration timing
            hashlib.pbkdf2_hmac("sha256", b"x", b"y", PBKDF2_ITERATIONS)
            return False
        try:
            algorithm, iterations, salt_hex, digest_hex = row["password_hash"].split("$")
        except ValueError:
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(candidate.hex(), digest_hex)

    def username(self) -> str | None:
        row = self.db.query_one("SELECT username FROM users LIMIT 1")
        return row["username"] if row else None

    # -- sessions ---------------------------------------------------------------

    def login(self, username: str, password: str) -> str:
        """Verify credentials and return a new session token."""
        if not self.verify_credentials(username, password):
            raise AuthError("Invalid username or password")
        token = SecretStore.new_token()
        self.db.execute(
            "INSERT INTO auth_sessions (token, username, created_at, expires_at) VALUES (?,?,?,?)",
            (token, username.strip(), now(), now() + SESSION_TTL_SECONDS),
        )
        self._purge_sessions()
        return token

    def validate_session(self, token: str | None) -> str | None:
        """Return the username for a valid, unexpired token."""
        if not token:
            return None
        row = self.db.query_one(
            "SELECT username, expires_at FROM auth_sessions WHERE token = ?", (token,)
        )
        if row is None:
            return None
        if row["expires_at"] < now():
            self.db.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
            return None
        return row["username"]

    def logout(self, token: str | None) -> None:
        if token:
            self.db.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))

    def _purge_sessions(self) -> None:
        self.db.execute("DELETE FROM auth_sessions WHERE expires_at < ?", (now(),))
