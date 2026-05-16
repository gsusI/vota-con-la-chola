from __future__ import annotations

from pathlib import Path
from typing import Any

from publicdata_core.fetch import detect_extension as _detect_extension
from publicdata_core.fetch import fetch_payload as _fetch_payload

from .config import BASE_HEADERS, SOURCE_CONFIG


def detect_extension(source_id: str, content_type: str | None, fallback_format: str) -> str:
    return _detect_extension(SOURCE_CONFIG, source_id, content_type, fallback_format)


def fetch_payload(
    source_id: str,
    source_url: str,
    raw_dir: Path,
    timeout: int,
    from_file: Path | None,
    strict_network: bool,
    *,
    insecure_ssl: bool = False,
) -> dict[str, Any]:
    return _fetch_payload(
        SOURCE_CONFIG,
        source_id,
        source_url,
        raw_dir,
        timeout,
        from_file,
        strict_network,
        base_headers=BASE_HEADERS,
        insecure_ssl=insecure_ssl,
    )


__all__ = ["detect_extension", "fetch_payload"]
