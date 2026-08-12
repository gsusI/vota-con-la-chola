"""Bounded-memory, content-addressed storage for large public documents."""

from __future__ import annotations

import hashlib
import os
import re
import ssl
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlparse

from .http import DEFAULT_HEADERS, DEFAULT_RETRYABLE_HTTP_CODES, retry_delay_seconds

DEFAULT_CHUNK_BYTES = 1024 * 1024
DEFAULT_MAX_BYTES = 250 * 1024 * 1024


@dataclass(frozen=True)
class StoredBlob:
    content_sha256: str
    bytes: int
    path: Path
    content_type: str | None
    etag: str | None
    last_modified: str | None
    deduplicated: bool


def _header(headers: object, name: str) -> str | None:
    getter = getattr(headers, "get", None)
    if getter is None:
        return None
    value = getter(name)
    token = str(value or "").strip()
    return token or None


def _safe_extension(url: str, content_type: str | None) -> str:
    normalized_type = str(content_type or "").split(";", 1)[0].strip().lower()
    known = {
        "application/pdf": ".pdf",
        "application/json": ".json",
        "application/xml": ".xml",
        "text/xml": ".xml",
        "text/html": ".html",
        "text/plain": ".txt",
        "application/zip": ".zip",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    }
    if normalized_type in known:
        return known[normalized_type]
    suffix = Path(urlparse(str(url)).path).suffix.lower()
    if re.fullmatch(r"\.[a-z0-9]{1,8}", suffix or ""):
        return suffix
    return ".bin"


def stream_response_to_content_addressed_store(
    response: BinaryIO,
    *,
    url: str,
    store_root: Path,
    max_bytes: int = DEFAULT_MAX_BYTES,
    chunk_bytes: int = DEFAULT_CHUNK_BYTES,
    progress_callback: Callable[[], None] | None = None,
) -> StoredBlob:
    """Stream one HTTP-like response to a SHA-256 path using atomic publish."""

    if int(max_bytes) < 1 or int(chunk_bytes) < 1:
        raise ValueError("max_bytes and chunk_bytes must be >= 1")
    headers = getattr(response, "headers", {})
    content_type = _header(headers, "Content-Type")
    content_length = _header(headers, "Content-Length")
    declared_bytes: int | None = None
    if content_length:
        try:
            candidate_bytes = int(content_length)
        except ValueError:
            candidate_bytes = -1
        if candidate_bytes >= 0:
            declared_bytes = candidate_bytes
        if declared_bytes is not None and declared_bytes > int(max_bytes):
            raise RuntimeError(
                f"download exceeds max_bytes before transfer: declared={declared_bytes} max={int(max_bytes)}"
            )

    partial_root = Path(store_root) / ".partial"
    partial_root.mkdir(parents=True, exist_ok=True)
    partial_path = partial_root / f"{uuid.uuid4().hex}.part"
    digest = hashlib.sha256()
    bytes_written = 0
    try:
        with partial_path.open("xb") as handle:
            while True:
                chunk = response.read(int(chunk_bytes))
                if not chunk:
                    break
                if not isinstance(chunk, (bytes, bytearray)):
                    raise TypeError("response.read() must return bytes")
                bytes_written += len(chunk)
                if bytes_written > int(max_bytes):
                    raise RuntimeError(
                        f"download exceeds max_bytes: received>{int(max_bytes)}"
                    )
                digest.update(chunk)
                handle.write(chunk)
                if progress_callback is not None:
                    progress_callback()
            if declared_bytes is not None and bytes_written != declared_bytes:
                raise RuntimeError(
                    "incomplete download: "
                    f"declared={declared_bytes} received={bytes_written}"
                )
            handle.flush()
            os.fsync(handle.fileno())

        content_sha256 = digest.hexdigest()
        extension = _safe_extension(url, content_type)
        final_path = (
            Path(store_root)
            / content_sha256[:2]
            / content_sha256[2:4]
            / f"{content_sha256}{extension}"
        )
        final_path.parent.mkdir(parents=True, exist_ok=True)
        deduplicated = final_path.exists()
        if deduplicated:
            partial_path.unlink(missing_ok=True)
        else:
            os.replace(partial_path, final_path)
        return StoredBlob(
            content_sha256=content_sha256,
            bytes=bytes_written,
            path=final_path,
            content_type=content_type,
            etag=_header(headers, "ETag"),
            last_modified=_header(headers, "Last-Modified"),
            deduplicated=deduplicated,
        )
    except Exception:
        partial_path.unlink(missing_ok=True)
        raise


def download_to_content_addressed_store(
    url: str,
    *,
    store_root: Path,
    timeout: int,
    headers: Mapping[str, str] | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    chunk_bytes: int = DEFAULT_CHUNK_BYTES,
    max_attempts: int = 3,
    retryable_http_codes: set[int] | None = None,
    ca_bundle: Path | None = None,
    insecure_ssl: bool = False,
    progress_callback: Callable[[], None] | None = None,
) -> StoredBlob:
    """Download one URL without retaining its body in memory."""

    if ca_bundle is not None and insecure_ssl:
        raise ValueError("ca_bundle and insecure_ssl are mutually exclusive")
    ssl_context: ssl.SSLContext | None = None
    if str(url).lower().startswith("https://"):
        if ca_bundle is not None:
            bundle_path = Path(ca_bundle)
            if not bundle_path.is_file():
                raise FileNotFoundError(bundle_path)
            ssl_context = ssl.create_default_context(cafile=str(bundle_path))
        elif insecure_ssl:
            ssl_context = ssl._create_unverified_context()

    request_headers = dict(DEFAULT_HEADERS)
    request_headers.update(
        {
            "Accept": "application/pdf,text/html,application/xml,text/xml,application/json,*/*",
        }
    )
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(str(url), headers=request_headers)
    retryable_codes = set(retryable_http_codes or DEFAULT_RETRYABLE_HTTP_CODES)
    attempts = max(1, int(max_attempts))
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        retry_after: str | None = None
        try:
            with urllib.request.urlopen(
                request,
                timeout=max(1, int(timeout)),
                context=ssl_context,
            ) as response:
                return stream_response_to_content_addressed_store(
                    response,
                    url=str(url),
                    store_root=Path(store_root),
                    max_bytes=int(max_bytes),
                    chunk_bytes=int(chunk_bytes),
                    progress_callback=progress_callback,
                )
        except urllib.error.HTTPError as exc:
            last_error = exc
            retry_after = _header(exc.headers, "Retry-After")
            should_retry = exc.code in retryable_codes and attempt < attempts
            exc.close()
            if not should_retry:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
            if attempt >= attempts:
                raise
        import time

        time.sleep(retry_delay_seconds(attempt, retry_after=retry_after))

    if last_error is not None:
        raise last_error
    raise RuntimeError("download failed without an exception")
