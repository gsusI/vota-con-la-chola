from __future__ import annotations

from pathlib import Path
from typing import Any

from publicdata_core.fetch import fetch_payload as _fetch_payload

from etl.politicos_es.config import BASE_HEADERS

from .config import SOURCE_CONFIG


def fetch_payload(
    source_id: str,
    source_url: str,
    raw_dir: Path,
    timeout: int,
    from_file: Path | None,
    strict_network: bool,
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
    )


__all__ = ["fetch_payload"]
