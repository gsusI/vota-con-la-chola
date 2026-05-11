from __future__ import annotations

import gzip

from publicdata_core.util import normalize_ws


def canonical_url(url: str) -> str:
    token = normalize_ws(url)
    if not token:
        return ""
    return token.split("#", 1)[0]


def dedupe_keep_order(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        token = normalize_ws(str(raw or ""))
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def maybe_decompress_gzip_payload(payload: bytes) -> bytes:
    if not payload.startswith(b"\x1f\x8b"):
        return payload
    try:
        return gzip.decompress(payload)
    except Exception:
        return payload


def exception_http_status(exc: Exception) -> int | None:
    if hasattr(exc, "code"):
        try:
            return int(getattr(exc, "code"))
        except Exception:  # noqa: BLE001
            return None
    return None
