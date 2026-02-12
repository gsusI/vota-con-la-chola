from __future__ import annotations

from pathlib import Path
from typing import Any

from etl.politicos_es.util import now_utc_iso, sha256_bytes

from .config import SOURCE_CONFIG
from .http import http_get_bytes, payload_looks_like_html
from .raw import fallback_payload_from_sample, raw_output_path


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

            # Default guardrail: only reject HTML when the source is not meant to be HTML.
            expected = str(SOURCE_CONFIG[source_id].get("format") or "").lower()
            if expected != "html" and ("html" in (content_type or "").lower() or payload_looks_like_html(payload)):
                raise RuntimeError(
                    f"Respuesta HTML inesperada para {source_id} (content_type={content_type or 'desconocido'})"
                )
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

