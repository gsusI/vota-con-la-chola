from __future__ import annotations

import publicdata_core.http as _core_http

from etl.politicos_es.config import BASE_HEADERS

random = _core_http.random
time = _core_http.time
urllib = _core_http.urllib

payload_looks_like_html = _core_http.payload_looks_like_html
validate_network_payload = _core_http.validate_network_payload


def http_get_bytes(
    url: str,
    timeout: int,
    headers: dict[str, str] | None = None,
    *,
    insecure_ssl: bool = False,
) -> tuple[bytes, str | None]:
    return _core_http.http_get_bytes(
        url,
        timeout,
        headers=headers,
        insecure_ssl=insecure_ssl,
        base_headers=BASE_HEADERS,
    )


__all__ = ["http_get_bytes", "payload_looks_like_html", "validate_network_payload"]
