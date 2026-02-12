from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from .config import SOURCE_CONFIG
from .util import now_utc_iso, sha256_bytes


def raw_output_path(raw_dir: Path, source_id: str, ext: str) -> Path:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    date_part = dt.datetime.now(dt.timezone.utc).strftime("%Y/%m/%d")
    path = raw_dir / source_id / date_part / f"{source_id}_{stamp}.{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def fallback_payload_from_sample(source_id: str, raw_dir: Path, note: str) -> dict[str, Any]:
    cfg = SOURCE_CONFIG[source_id]
    sample_path = Path(cfg["fallback_file"])
    if not sample_path.exists():
        raise RuntimeError(f"Fallback no disponible para {source_id}: {sample_path}")

    payload = sample_path.read_bytes()
    ext = sample_path.suffix.lstrip(".") or cfg["format"]
    fetched_at = now_utc_iso()
    raw_path = raw_output_path(raw_dir, source_id, ext)
    raw_path.write_bytes(payload)
    return {
        "source_url": f"file://{sample_path.resolve()}",
        "resolved_url": f"file://{sample_path.resolve()}",
        "fetched_at": fetched_at,
        "raw_path": raw_path,
        "content_sha256": sha256_bytes(payload),
        "content_type": None,
        "bytes": len(payload),
        "payload": payload,
        "note": note,
    }

