from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Callable

from publicdata_core.fetch import fetch_payload
from publicdata_core.types import Extracted
from publicdata_core.util import now_utc_iso, pick_value, sha256_bytes, stable_json

from .config import SOURCE_CONFIG


Parser = Callable[[bytes], list[dict[str, Any]]]


def _parser_module_name(source_id: str) -> str:
    return f"publicdata_connectors_es.contrib.parsers.{source_id}"


def _load_parser(source_id: str) -> Parser:
    module = importlib.import_module(_parser_module_name(source_id))
    parser = getattr(module, "parse_records", None)
    if not callable(parser):
        raise RuntimeError(f"Parser missing parse_records(payload: bytes): {module.__name__}")
    return parser


def _fallback_json_parser(payload: bytes) -> list[dict[str, Any]]:
    parsed = json.loads(payload.decode("utf-8"))
    if isinstance(parsed, dict):
        records = parsed.get("records")
        if isinstance(records, list):
            return [record for record in records if isinstance(record, dict)]
        return [parsed]
    if isinstance(parsed, list):
        return [record for record in parsed if isinstance(record, dict)]
    return []


class ContribSourceRecordsConnector:
    """Generic onboarding connector for scaffolded sources.

    It persists traceable source_records first. Domain-specific normalization can be added later
    without changing the onboarding contract.
    """

    ingest_mode = "source_records_only"

    def __init__(self, source_id: str):
        if source_id not in SOURCE_CONFIG:
            raise KeyError(f"Unknown contrib source_id: {source_id}")
        self.source_id = source_id

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        del timeout
        return url_override or str(SOURCE_CONFIG[self.source_id]["default_url"])

    def extract(
        self,
        raw_dir: Path,
        timeout: int,
        from_file: Path | None,
        url_override: str | None,
        strict_network: bool,
        options: dict[str, Any] | None = None,
    ) -> Extracted:
        del options
        source_url = self.resolve_url(url_override, timeout)
        fetched = fetch_payload(
            SOURCE_CONFIG,
            self.source_id,
            source_url,
            raw_dir,
            timeout,
            from_file,
            strict_network,
        )
        parser = _load_parser(self.source_id)
        records = parser(fetched["payload"])
        if not records and str(SOURCE_CONFIG[self.source_id].get("format", "")).lower() == "json":
            records = _fallback_json_parser(fetched["payload"])
        return Extracted(
            source_id=self.source_id,
            source_url=str(fetched["source_url"]),
            resolved_url=str(fetched["resolved_url"]),
            fetched_at=str(fetched["fetched_at"]),
            raw_path=Path(fetched["raw_path"]),
            content_sha256=str(fetched["content_sha256"]),
            content_type=fetched.get("content_type"),
            bytes=int(fetched["bytes"]),
            note=str(fetched["note"]),
            payload=bytes(fetched["payload"]),
            records=records,
        )

    def normalize(self, record: dict[str, Any], snapshot_date: str | None) -> dict[str, Any] | None:
        if not isinstance(record, dict):
            return None
        source_record_id = (
            pick_value(record, ("source_record_id", "record_id", "id", "url", "source_url"))
            or sha256_bytes(stable_json(record).encode("utf-8"))[:16]
        )
        return {
            "source_record_id": source_record_id,
            "source_snapshot_date": snapshot_date or now_utc_iso()[:10],
            "raw_payload": stable_json(record),
        }


def get_contrib_connectors() -> dict[str, ContribSourceRecordsConnector]:
    return {source_id: ContribSourceRecordsConnector(source_id) for source_id in sorted(SOURCE_CONFIG)}
