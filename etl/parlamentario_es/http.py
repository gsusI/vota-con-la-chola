from __future__ import annotations

import ssl
import time
import urllib.error
import urllib.request

from etl.politicos_es.config import BASE_HEADERS


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

    for attempt in range(1, 4):
        try:
            if context is not None:
                with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                    return response.read(), response.headers.get("Content-Type")
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read(), response.headers.get("Content-Type")
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code not in {429, 500, 502, 503, 504} or attempt >= 3:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_exc = exc
            if attempt >= 3:
                raise
        time.sleep(1.0 * attempt)

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("http_get_bytes: error inesperado")


def payload_looks_like_html(payload: bytes) -> bool:
    sample = payload[:4096].lstrip().lower()
    if sample.startswith(b"<!doctype html") or sample.startswith(b"<html"):
        return True
    return b"<html" in sample[:1024] or b"<head" in sample[:1024]

