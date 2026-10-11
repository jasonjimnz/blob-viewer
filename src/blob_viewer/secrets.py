"""Encrypted credential storage.

Design goals:

* Credentials (S3 access keys, secret keys) are stored **encrypted at rest**
  inside the application folder — never as plain text.
* The API never returns secret values; secrets are *redacted* to a masked
  form (e.g. ``••••abcd``) so the UI can show that a value exists without
  exposing it.
* A random Fernet key is generated once per installation and stored in
  ``<home>/secrets.key`` with restrictive permissions.  Whoever can read that
  file (i.e. the OS user running Blob Viewer) can decrypt the database; anyone
  else — including other local users — cannot.
"""

from __future__ import annotations

import os
import secrets as _secrets
import stat
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class SecretStore:
    """Encrypts and decrypts secret values using a per-installation key."""

    def __init__(self, key_path: Path) -> None:
        self.key_path = Path(key_path)
        self._fernet: Fernet | None = None

    def _load_key(self) -> bytes:
        if self.key_path.exists():
            return self.key_path.read_bytes().strip()
        key = Fernet.generate_key()
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        self.key_path.write_bytes(key)
        _restrict(self.key_path)
        return key

    @property
    def fernet(self) -> Fernet:
        if self._fernet is None:
            self._fernet = Fernet(self._load_key())
        return self._fernet

    def encrypt(self, value: str) -> bytes:
        return self.fernet.encrypt(value.encode("utf-8"))

    def decrypt(self, ciphertext: bytes) -> str:
        try:
            return self.fernet.decrypt(bytes(ciphertext)).decode("utf-8")
        except InvalidToken as exc:  # pragma: no cover - corrupt key/file
            raise RuntimeError(
                "Cannot decrypt stored credentials. The secrets.key file may "
                "have been regenerated. Re-enter the affected workspace credentials."
            ) from exc

    @staticmethod
    def redact(value: str | None) -> str | None:
        """Mask a secret, keeping only the last 4 characters visible."""
        if not value:
            return None
        if len(value) <= 4:
            return "••••"
        return "••••" + value[-4:]

    @staticmethod
    def new_token(nbytes: int = 32) -> str:
        return _secrets.token_urlsafe(nbytes)


def _restrict(path: Path) -> None:
    if os.name == "posix":
        try:
            path.chmod(stat.S_IRUSR | stat.IWUSR)
        except OSError:
            pass
