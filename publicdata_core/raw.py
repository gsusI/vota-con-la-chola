from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def raw_output_path(raw_dir: Path, source_id: str, ext: str) -> Path:
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    date_part = dt.datetime.now(dt.UTC).strftime("%Y/%m/%d")
    path = raw_dir / source_id / date_part / f"{source_id}_{stamp}.{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def fallback_payload_from_sample(
    source_config: Mapping[str, Mapping[str, Any]],
    source_id: str,
    raw_dir: Path,
    note: str,
) -> dict[str, Any]:
    _ = source_config
    _ = raw_dir
    _ = note
    raise RuntimeError(
        "Implicit sample fallback is disabled by the real-data-only policy "
        f"for {source_id}. Fix the official network source or pass a verified "
        "official capture explicitly with --from-file."
    )
