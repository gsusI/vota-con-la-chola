from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Extracted:
    source_id: str
    source_url: str
    resolved_url: str
    fetched_at: str
    raw_path: Path
    content_sha256: str
    content_type: str | None
    bytes: int
    note: str
    payload: bytes
    records: list[dict[str, Any]]

