from __future__ import annotations

from publicdata_core.http import payload_looks_like_html, validate_network_payload
from publicdata_core.http import http_get_bytes as _http_get_bytes

from .config import BASE_HEADERS


def http_get_bytes(
    url: str,
    timeout: int,
    headers: dict[str, str] | None = None,
    *,
    insecure_ssl: bool = False,
) -> tuple[bytes, str | None]:
    return _http_get_bytes(
        url,
        timeout,
        headers=headers,
        insecure_ssl=insecure_ssl,
        base_headers=BASE_HEADERS,
    )


__all__ = ["http_get_bytes", "payload_looks_like_html", "validate_network_payload"]
