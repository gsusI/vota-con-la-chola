from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import SOURCE_CONFIG
from .http import http_get_bytes, validate_network_payload
from .raw import fallback_payload_from_sample, raw_output_path
from .util import now_utc_iso, sha256_bytes


def detect_extension(source_id: str, content_type: str | None, fallback_format: str) -> str:
    if content_type:
        content_type = content_type.lower()
        if "spreadsheetml" in content_type or "ms-excel" in content_type:
            return "xlsx"
        if "json" in content_type:
            return "json"
        if "csv" in content_type:
            return "csv"
        if "xml" in content_type:
            return "xml"
    cfg = SOURCE_CONFIG[source_id]
    return cfg.get("format", fallback_format)


def fetch_payload(
    source_id: str,
    source_url: str,
    raw_dir: Path,
    timeout: int,
    from_file: Path | None,
    strict_network: bool,
) -> dict[str, Any]:
    fetched_at = now_utc_iso()
    ext = SOURCE_CONFIG[source_id]["format"]
    content_type = None

    if from_file:
        payload = from_file.read_bytes()
        ext = from_file.suffix.lstrip(".") or ext
        resolved_url = f"file://{from_file.resolve()}"
        source_url = resolved_url
        note = "from-file"
    else:
        resolved_url = source_url
        note = "network"
        try:
            payload, content_type = http_get_bytes(source_url, timeout)
            validate_network_payload(source_id, payload, content_type)
            ext = detect_extension(source_id, content_type, ext)
        except Exception as exc:  # noqa: BLE001
            if strict_network:
                raise
            return fallback_payload_from_sample(
                source_id,
                raw_dir,
                note=f"network-error-fallback: {type(exc).__name__}: {exc}",
            )

    raw_path = raw_output_path(raw_dir, source_id, ext)
    raw_path.write_bytes(payload)

    return {
        "source_url": source_url,
        "resolved_url": resolved_url,
        "fetched_at": fetched_at,
        "raw_path": raw_path,
        "content_sha256": sha256_bytes(payload),
        "content_type": content_type,
        "bytes": len(payload),
        "payload": payload,
        "note": note,
    }

