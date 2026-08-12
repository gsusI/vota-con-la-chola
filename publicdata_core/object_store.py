"""Checksum-verified content-addressed durable object-store contract."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, BinaryIO, Protocol


DEFAULT_MAX_OBJECT_BYTES = 2 * 1024 * 1024 * 1024
DEFAULT_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class ObjectReplica:
    backend: str
    bucket: str
    object_key: str
    content_sha256: str
    bytes: int
    content_type: str | None
    version_id: str | None
    deduplicated: bool

    def as_manifest_row(self) -> dict[str, object]:
        return asdict(self)


class ContentObjectStore(Protocol):
    def put_verified(
        self,
        path: Path,
        *,
        content_sha256: str,
        bytes_expected: int,
        content_type: str | None = None,
        namespace: str = "raw",
    ) -> ObjectReplica: ...

    def restore_verified(
        self,
        replica: ObjectReplica,
        *,
        destination: Path,
        max_bytes: int = DEFAULT_MAX_OBJECT_BYTES,
    ) -> Path: ...


def content_addressed_object_key(namespace: str, content_sha256: str) -> str:
    digest = str(content_sha256 or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("content_sha256 must be 64 lowercase hex characters")
    clean_namespace = re.sub(r"[^a-zA-Z0-9._/-]+", "-", str(namespace or "raw"))
    clean_namespace = clean_namespace.strip("/.") or "raw"
    if ".." in clean_namespace.split("/"):
        raise ValueError("namespace cannot contain parent traversal")
    return f"{clean_namespace}/sha256/{digest[:2]}/{digest[2:4]}/{digest}"


def hash_file(path: Path, *, chunk_bytes: int = DEFAULT_CHUNK_BYTES) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(int(chunk_bytes))
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
    return digest.hexdigest(), total


def _verify_local_source(
    path: Path, *, content_sha256: str, bytes_expected: int
) -> None:
    actual_sha256, actual_bytes = hash_file(path)
    if actual_sha256 != str(content_sha256).lower():
        raise RuntimeError(
            f"source checksum mismatch: expected={content_sha256} actual={actual_sha256}"
        )
    if actual_bytes != int(bytes_expected):
        raise RuntimeError(
            f"source byte count mismatch: expected={bytes_expected} actual={actual_bytes}"
        )


class FilesystemObjectStore:
    """Durable-origin contract backed by another filesystem for local drills."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def put_verified(
        self,
        path: Path,
        *,
        content_sha256: str,
        bytes_expected: int,
        content_type: str | None = None,
        namespace: str = "raw",
    ) -> ObjectReplica:
        _verify_local_source(
            Path(path),
            content_sha256=content_sha256,
            bytes_expected=bytes_expected,
        )
        key = content_addressed_object_key(namespace, content_sha256)
        target = self.root / key
        deduplicated = target.is_file()
        if deduplicated:
            _verify_local_source(
                target,
                content_sha256=content_sha256,
                bytes_expected=bytes_expected,
            )
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_name(f".{target.name}.{uuid.uuid4().hex}.partial")
            try:
                with Path(path).open("rb") as source, partial.open("xb") as destination:
                    shutil.copyfileobj(source, destination, length=DEFAULT_CHUNK_BYTES)
                    destination.flush()
                    os.fsync(destination.fileno())
                _verify_local_source(
                    partial,
                    content_sha256=content_sha256,
                    bytes_expected=bytes_expected,
                )
                os.replace(partial, target)
            except Exception:
                partial.unlink(missing_ok=True)
                raise
        return ObjectReplica(
            backend="filesystem",
            bucket="filesystem-origin",
            object_key=key,
            content_sha256=str(content_sha256).lower(),
            bytes=int(bytes_expected),
            content_type=content_type,
            version_id=None,
            deduplicated=deduplicated,
        )

    def restore_verified(
        self,
        replica: ObjectReplica,
        *,
        destination: Path,
        max_bytes: int = DEFAULT_MAX_OBJECT_BYTES,
    ) -> Path:
        if int(replica.bytes) > int(max_bytes):
            raise RuntimeError("object exceeds restore max_bytes")
        source = self.root / replica.object_key
        _verify_local_source(
            source,
            content_sha256=replica.content_sha256,
            bytes_expected=replica.bytes,
        )
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.partial")
        try:
            with source.open("rb") as source_handle, partial.open("xb") as target:
                shutil.copyfileobj(source_handle, target, length=DEFAULT_CHUNK_BYTES)
                target.flush()
                os.fsync(target.fileno())
            _verify_local_source(
                partial,
                content_sha256=replica.content_sha256,
                bytes_expected=replica.bytes,
            )
            os.replace(partial, destination)
        except Exception:
            partial.unlink(missing_ok=True)
            raise
        return destination


class _BoundedHashWriter:
    def __init__(self, handle: BinaryIO, max_bytes: int) -> None:
        self.handle = handle
        self.max_bytes = int(max_bytes)
        self.digest = hashlib.sha256()
        self.bytes = 0

    def write(self, chunk: bytes) -> int:
        self.bytes += len(chunk)
        if self.bytes > self.max_bytes:
            raise RuntimeError("object exceeds restore max_bytes during transfer")
        self.digest.update(chunk)
        return self.handle.write(chunk)

    def flush(self) -> None:
        self.handle.flush()


class S3ObjectStore:
    """S3-compatible origin using an injected or lazily-created boto3 client."""

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None = None,
        region_name: str | None = None,
        client: Any | None = None,
    ) -> None:
        if not str(bucket or "").strip():
            raise ValueError("bucket is required")
        self.bucket = str(bucket).strip()
        if client is None:
            try:
                import boto3  # type: ignore[import-not-found]
            except ImportError as exc:
                raise RuntimeError(
                    "S3 backend requires optional dependency: pip install '.[object-store]'"
                ) from exc
            client = boto3.client(
                "s3",
                endpoint_url=endpoint_url or None,
                region_name=region_name or None,
            )
        self.client = client

    def _head(self, key: str) -> dict[str, Any] | None:
        try:
            return dict(self.client.head_object(Bucket=self.bucket, Key=key))
        except Exception as exc:  # noqa: BLE001
            response = getattr(exc, "response", {}) or {}
            status = ((response.get("ResponseMetadata") or {}).get("HTTPStatusCode"))
            code = str((response.get("Error") or {}).get("Code") or "")
            if status == 404 or code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise

    @staticmethod
    def _verify_head(
        head: dict[str, Any], *, content_sha256: str, bytes_expected: int
    ) -> None:
        metadata = {str(k).lower(): str(v) for k, v in dict(head.get("Metadata") or {}).items()}
        remote_sha256 = metadata.get("sha256")
        if remote_sha256 != str(content_sha256).lower():
            raise RuntimeError(
                f"remote checksum metadata mismatch: expected={content_sha256} actual={remote_sha256}"
            )
        remote_bytes = int(head.get("ContentLength") or -1)
        if remote_bytes != int(bytes_expected):
            raise RuntimeError(
                f"remote byte count mismatch: expected={bytes_expected} actual={remote_bytes}"
            )

    def put_verified(
        self,
        path: Path,
        *,
        content_sha256: str,
        bytes_expected: int,
        content_type: str | None = None,
        namespace: str = "raw",
    ) -> ObjectReplica:
        _verify_local_source(
            Path(path),
            content_sha256=content_sha256,
            bytes_expected=bytes_expected,
        )
        key = content_addressed_object_key(namespace, content_sha256)
        head = self._head(key)
        deduplicated = head is not None
        if head is None:
            extra_args: dict[str, Any] = {
                "Metadata": {"sha256": str(content_sha256).lower()},
            }
            if content_type:
                extra_args["ContentType"] = str(content_type)
            with Path(path).open("rb") as handle:
                self.client.upload_fileobj(
                    handle,
                    self.bucket,
                    key,
                    ExtraArgs=extra_args,
                )
            head = self._head(key)
            if head is None:
                raise RuntimeError("remote object missing after upload")
        self._verify_head(
            head,
            content_sha256=content_sha256,
            bytes_expected=bytes_expected,
        )
        return ObjectReplica(
            backend="s3",
            bucket=self.bucket,
            object_key=key,
            content_sha256=str(content_sha256).lower(),
            bytes=int(bytes_expected),
            content_type=content_type,
            version_id=str(head.get("VersionId") or "") or None,
            deduplicated=deduplicated,
        )

    def restore_verified(
        self,
        replica: ObjectReplica,
        *,
        destination: Path,
        max_bytes: int = DEFAULT_MAX_OBJECT_BYTES,
    ) -> Path:
        if replica.bucket != self.bucket:
            raise ValueError("replica bucket does not match configured bucket")
        if int(replica.bytes) > int(max_bytes):
            raise RuntimeError("object exceeds restore max_bytes")
        head = self._head(replica.object_key)
        if head is None:
            raise FileNotFoundError(replica.object_key)
        self._verify_head(
            head,
            content_sha256=replica.content_sha256,
            bytes_expected=replica.bytes,
        )
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.partial")
        try:
            with partial.open("xb") as handle:
                writer = _BoundedHashWriter(handle, int(max_bytes))
                self.client.download_fileobj(self.bucket, replica.object_key, writer)
                writer.flush()
                os.fsync(handle.fileno())
            if writer.bytes != int(replica.bytes):
                raise RuntimeError("restored byte count mismatch")
            if writer.digest.hexdigest() != replica.content_sha256:
                raise RuntimeError("restored checksum mismatch")
            os.replace(partial, destination)
        except Exception:
            partial.unlink(missing_ok=True)
            raise
        return destination
