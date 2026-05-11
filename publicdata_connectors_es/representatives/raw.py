from __future__ import annotations

from pathlib import Path
from typing import Any

from publicdata_core.raw import fallback_payload_from_sample as _fallback_payload_from_sample
from publicdata_core.raw import raw_output_path

from .config import SOURCE_CONFIG


def fallback_payload_from_sample(source_id: str, raw_dir: Path, note: str) -> dict[str, Any]:
    return _fallback_payload_from_sample(SOURCE_CONFIG, source_id, raw_dir, note=note)


__all__ = ["fallback_payload_from_sample", "raw_output_path"]
