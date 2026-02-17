from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ..types import Extracted


class BaseConnector(ABC):
    source_id: str
    # Default ingest behavior writes source_records + mandates.
    # Connectors can override this with "source_records_only" when they do not map to persons/mandates.
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
    ) -> Extracted:
        raise NotImplementedError

    @abstractmethod
    def normalize(self, record: dict[str, Any], snapshot_date: str | None) -> dict[str, Any] | None:
        raise NotImplementedError
