from __future__ import annotations

import ssl
import time
import random
from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Mapping
import urllib.error
import urllib.request


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

DEFAULT_RETRYABLE_HTTP_CODES = {408, 429, 500, 502, 503, 504}


def parse_retry_after_seconds(value: str | None) -> float | None:
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


def retry_delay_seconds(
    attempt: int,
    retry_after: str | None = None,
    *,
    base_backoff_seconds: float = 1.0,
    jitter_max_seconds: float = 0.25,
) -> float:
    parsed_retry_after = parse_retry_after_seconds(retry_after)
    if parsed_retry_after is not None:
        return parsed_retry_after
    base = float(base_backoff_seconds) * (2 ** (int(attempt) - 1))
    return base + random.uniform(0.0, float(jitter_max_seconds))


def payload_looks_like_html(payload: bytes) -> bool:
    sample = payload[:4096].lstrip().lower()
    if sample.startswith(b"<!doctype html") or sample.startswith(b"<html"):
        return True
    return b"<html" in sample[:1024] or b"<head" in sample[:1024]


def validate_network_payload(source_id: str, payload: bytes, content_type: str | None) -> None:
    lower_ct = (content_type or "").lower()
    if "html" in lower_ct or payload_looks_like_html(payload):
        raise RuntimeError(
            f"Respuesta HTML inesperada para {source_id} "
            f"(content_type={content_type or 'desconocido'})"
        )


def http_get_bytes(
    url: str,
    timeout: int,
    headers: Mapping[str, str] | None = None,
    *,
    insecure_ssl: bool = False,
    base_headers: Mapping[str, str] | None = None,
    max_attempts: int = 3,
    retryable_http_codes: set[int] | None = None,
) -> tuple[bytes, str | None]:
    request_headers = dict(base_headers or DEFAULT_HEADERS)
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, headers=request_headers)
    last_exc: Exception | None = None
    context = None
    if insecure_ssl and url.lower().startswith("https://"):
        context = ssl._create_unverified_context()  # noqa: S501
    attempts = max(1, int(max_attempts))
    retryable_codes = set(retryable_http_codes or DEFAULT_RETRYABLE_HTTP_CODES)
    for attempt in range(1, attempts + 1):
        retry_after_header: str | None = None
        try:
            if context is not None:
                with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                    return response.read(), response.headers.get("Content-Type")
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read(), response.headers.get("Content-Type")
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code not in retryable_codes or attempt >= attempts:
                raise
            if exc.headers is not None:
                retry_after_header = exc.headers.get("Retry-After")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_exc = exc
            if attempt >= attempts:
                raise
        time.sleep(retry_delay_seconds(attempt, retry_after=retry_after_header))
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("http_get_bytes: error inesperado")
