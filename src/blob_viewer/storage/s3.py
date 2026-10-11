"""S3-compatible backend (AWS S3, MinIO, Backblaze B2, R2, Spaces, ...)."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Iterator
from urllib.parse import urlparse

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from .base import BlobEntry, NotFoundError, Storage, StorageError

_CLIENT_TIMEOUT = 60


class S3Storage(Storage):
    """Read-only storage bound to one bucket of an S3-compatible service."""

    def __init__(
        self,
        *,
        endpoint: str,
        bucket: str,
        access_key: str | None = None,
        secret_key: str | None = None,
        region: str | None = None,
        prefix: str = "",
        path_style: bool = True,
    ) -> None:
        self.bucket = bucket
        self.prefix = (prefix or "").strip("/")
        if self.prefix:
            self.prefix += "/"
        self.path_style = path_style
        parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
        addressing = "path" if path_style else "auto"
        try:
            self.client = boto3.client(
                "s3",
                endpoint_url=f"{parsed.scheme or 'https'}://{parsed.netloc}",
                region_name=region or "us-east-1",
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                config=Config(
                    signature_version="s3v4",
                    s3={"addressing_style": addressing},
                    connect_timeout=_CLIENT_TIMEOUT,
                    read_timeout=_CLIENT_TIMEOUT,
                    retries={"max_attempts": 3, "mode": "standard"},
                ),
            )
        except (BotoCoreError, ValueError) as exc:
            raise StorageError(f"Invalid S3 configuration: {exc}") from exc

    # -- helpers -------------------------------------------------------------

    def _full_key(self, key: str) -> str:
        key = key.lstrip("/")
        if not self.prefix:
            return key
        return self.prefix + key

    @staticmethod
    def _entry_from_s3(obj) -> BlobEntry:  # noqa: ANN001 - boto3 shape
        last_modified = obj.get("LastModified")
        return BlobEntry(
            key=obj["Key"],
            size=int(obj.get("Size", 0) or 0),
            last_modified=_to_ts(last_modified),
            etag=(obj.get("ETag") or "").strip('"') or None,
        )

    # -- reads ---------------------------------------------------------------

    def list_objects(self, prefix: str = "", delimiter: str = "/") -> tuple[list[BlobEntry], list[BlobEntry]]:
        full_prefix = self._full_key(prefix)
        files: list[BlobEntry] = []
        dirs: list[BlobEntry] = []
        paginator = self.client.get_paginator("list_objects_v2")
        try:
            for page in paginator.paginate(
                Bucket=self.bucket, Prefix=full_prefix, Delimiter=delimiter
            ):
                for cp in page.get("CommonPrefixes", []):
                    rel = cp["Prefix"][len(self.prefix):]
                    dirs.append(BlobEntry(key=rel, size=0, last_modified=None, etag=None, is_dir=True))
                for obj in page.get("Contents", []):
                    if obj["Key"].endswith("/"):
                        continue  # folder marker objects
                    rel = obj["Key"][len(self.prefix):]
                    files.append(self._entry_from_s3({**obj, "Key": rel}))
        except ClientError as exc:
            raise _translate(exc) from exc
        except BotoCoreError as exc:
            raise StorageError(f"S3 request failed: {exc}") from exc
        return files, dirs

    def get(self, key: str) -> BlobEntry:
        try:
            head = self.client.head_object(Bucket=self.bucket, Key=self._full_key(key))
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                raise NotFoundError(f"'{key}' does not exist in this workspace") from exc
            raise _translate(exc) from exc
        except BotoCoreError as exc:
            raise StorageError(f"S3 request failed: {exc}") from exc
        return BlobEntry(
            key=key,
            size=int(head.get("ContentLength", 0) or 0),
            last_modified=_to_ts(head.get("LastModified")),
            etag=(head.get("ETag") or "").strip('"') or None,
        )

    def iter_file(self, key: str, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
        try:
            resp = self.client.get_object(Bucket=self.bucket, Key=self._full_key(key))
            yield from resp["Body"].iter_chunks(chunk_size)
        except ClientError as exc:
            raise _translate(exc) from exc
        except BotoCoreError as exc:
            raise StorageError(f"S3 request failed: {exc}") from exc

    def open(self, key: str) -> BinaryIO:
        try:
            resp = self.client.get_object(Bucket=self.bucket, Key=self._full_key(key))
            return resp["Body"]  # type: ignore[return-value]
        except ClientError as exc:
            raise _translate(exc) from exc

    def download_to(self, key: str, dest_path: str) -> BlobEntry:
        tmp = dest_path + ".part"
        try:
            self.client.download_file(self.bucket, self._full_key(key), tmp)
            shutil.move(tmp, dest_path)
        except ClientError as exc:
            Path(tmp).unlink(missing_ok=True)
            raise _translate(exc) from exc
        except BotoCoreError as exc:
            Path(tmp).unlink(missing_ok=True)
            raise StorageError(f"S3 request failed: {exc}") from exc
        return self.get(key)

    def test_connection(self) -> dict:
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return {"ok": True, "message": f"Bucket '{self.bucket}' is reachable"}
        except ClientError as exc:
            raise _translate(exc) from exc


def _to_ts(dt: datetime | None) -> float | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _translate(exc: ClientError) -> StorageError:
    code = exc.response.get("Error", {}).get("Code", "")
    status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
    if code in ("404", "NoSuchKey", "NotFound", "NoSuchBucket") or status == 404:
        return NotFoundError(str(exc))
    if status in (401, 403):
        return StorageError("Access denied: check the workspace credentials")
    return StorageError(str(exc))
