from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .types import Extracted


class BaseConnector(ABC):
    source_id: str
    ingest_mode: str = "mandates"

    @abstractmethod
    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        raise NotImplementedError

    @abstractmethod
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
