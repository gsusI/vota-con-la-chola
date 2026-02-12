from __future__ import annotations

import random
import ssl
import time
import urllib.error
import urllib.request
from datetime import timezone
from email.utils import parsedate_to_datetime

from etl.politicos_es.config import BASE_HEADERS

_MAX_ATTEMPTS = 3
_RETRYABLE_HTTP_CODES = {408, 429, 500, 502, 503, 504}
_BASE_BACKOFF_SECONDS = 1.0
_JITTER_MAX_SECONDS = 0.25


def _parse_retry_after_seconds(value: str | None) -> float | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None

    try:
        delay = float(raw)
        return max(0.0, delay)
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(raw)
    except (TypeError, ValueError, OverflowError):
        return None

    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    return max(0.0, retry_at.timestamp() - time.time())


def _retry_delay_seconds(attempt: int, retry_after: str | None = None) -> float:
    parsed_retry_after = _parse_retry_after_seconds(retry_after)
    if parsed_retry_after is not None:
        return parsed_retry_after
    base = _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
    return base + random.uniform(0.0, _JITTER_MAX_SECONDS)


def http_get_bytes(
    url: str,
    timeout: int,
    headers: dict[str, str] | None = None,
    *,
    insecure_ssl: bool = False,
) -> tuple[bytes, str | None]:
    request_headers = dict(BASE_HEADERS)
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, headers=request_headers)

    last_exc: Exception | None = None
    context = None
    if insecure_ssl and url.lower().startswith("https://"):
        context = ssl._create_unverified_context()  # noqa: S501

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        retry_after_header: str | None = None
        try:
            if context is not None:
                with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                    return response.read(), response.headers.get("Content-Type")
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read(), response.headers.get("Content-Type")
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code not in _RETRYABLE_HTTP_CODES or attempt >= _MAX_ATTEMPTS:
                raise
            if exc.headers is not None:
                retry_after_header = exc.headers.get("Retry-After")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_exc = exc
            if attempt >= _MAX_ATTEMPTS:
                raise
        time.sleep(_retry_delay_seconds(attempt, retry_after=retry_after_header))

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("http_get_bytes: error inesperado")


def payload_looks_like_html(payload: bytes) -> bool:
    sample = payload[:4096].lstrip().lower()
    if sample.startswith(b"<!doctype html") or sample.startswith(b"<html"):
        return True
    return b"<html" in sample[:1024] or b"<head" in sample[:1024]
