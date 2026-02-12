from __future__ import annotations

from pathlib import Path
from typing import Any

from ..types import Extracted


class BaseConnector:
    source_id: str

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        raise NotImplementedError

    def extract(
        self,
        raw_dir: Path,
        timeout: int,
        from_file: Path | None,
        url_override: str | None,
        strict_network: bool,
        options: dict[str, Any] | None = None,
    ) -> Extracted:
        raise NotImplementedError

