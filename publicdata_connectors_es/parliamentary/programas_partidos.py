from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from publicdata_core.util import now_utc_iso, normalize_ws, sha256_bytes

from publicdata_connectors_es.parliamentary.config import SOURCE_CONFIG
from publicdata_core.raw import raw_output_path
from publicdata_core.types import Extracted
from publicdata_core.connectors import BaseConnector


class ProgramasPartidosConnector(BaseConnector):
    """Manifest-driven connector for party programs.

    v1 is intentionally minimal:
    - Reads a CSV manifest supplied explicitly with `--from-file`.
    - Does not fetch program documents here; ingestion/persistence happens in the pipeline.
    """

    source_id = "programas_partidos"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        if url_override:
            return url_override
        return str(SOURCE_CONFIG[self.source_id].get("default_url") or "")

    def extract(
        self,
        raw_dir: Path,
        timeout: int,
        from_file: Path | None,
        url_override: str | None,
        strict_network: bool,
        options: dict[str, Any] | None = None,
    ) -> Extracted:
        _ = timeout
        _ = url_override
        options = dict(options or {})
        max_records = options.get("max_records")

        if from_file is None:
            raise RuntimeError(
                "programas_partidos requires an explicit manifest of real official sources via --from-file"
            )
        manifest_path = from_file
        if not manifest_path.exists():
            raise RuntimeError(f"Manifest no existe para {self.source_id}: {manifest_path}")
        if manifest_path.is_dir():
            raise RuntimeError(f"Manifest debe ser archivo CSV, no directorio: {manifest_path}")

        payload_bytes = manifest_path.read_bytes()
        ext = manifest_path.suffix.lstrip(".") or "csv"
        raw_path = raw_output_path(raw_dir, self.source_id, ext)
        raw_path.write_bytes(payload_bytes)

        records: list[dict[str, Any]] = []
        try:
            with manifest_path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if not isinstance(row, dict):
                        continue
                    normalized: dict[str, Any] = {}
                    for k, v in row.items():
                        kk = normalize_ws(str(k or ""))
                        if not kk:
                            continue
                        normalized[kk] = normalize_ws(str(v or ""))
                    if not normalized:
                        continue
                    records.append({"payload": normalized})
        except Exception as exc:  # noqa: BLE001
            if strict_network:
                raise
            records = []

        if isinstance(max_records, int) and max_records > 0:
            records = records[: int(max_records)]

        resolved = f"file://{manifest_path.resolve()}"
        note = "from-file"
        return Extracted(
            source_id=self.source_id,
            source_url=resolved,
            resolved_url=resolved,
            fetched_at=now_utc_iso(),
            raw_path=raw_path,
            content_sha256=sha256_bytes(payload_bytes),
            content_type="text/csv",
            bytes=len(payload_bytes),
            note=note,
            payload=payload_bytes,
            records=records,
        )
