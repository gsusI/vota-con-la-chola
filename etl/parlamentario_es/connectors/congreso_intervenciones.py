from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from etl.politicos_es.util import now_utc_iso, sha256_bytes, stable_json

from ..config import SOURCE_CONFIG
from ..http import http_get_bytes
from ..raw import raw_output_path
from ..types import Extracted
from .base import BaseConnector


CONGRESO_BASE = "https://www.congreso.es"

# The catalog page contains export links like:
# /webpublica/opendata/intervenciones/IntervencionesIniciativa__YYYYMMDDHHMMSS.json
# /webpublica/opendata/intervenciones/IntervencionesCronologicamente__YYYYMMDDHHMMSS.json
INTERVENCIONES_JSON_RE = re.compile(
    r'(?P<href>/webpublica/opendata/intervenciones/[^"\' ]+__\d{14}\.json)\b'
)


def _parse_variant_from_url(url: str) -> str:
    name = Path(url).name
    return name.split("__", 1)[0] if "__" in name else name


class CongresoIntervencionesConnector(BaseConnector):
    source_id = "congreso_intervenciones"

    def resolve_url(self, url_override: str | None, timeout: int) -> str:
        _ = timeout
        return url_override or SOURCE_CONFIG[self.source_id]["default_url"]

    def extract(
        self,
        raw_dir: Path,
        timeout: int,
        from_file: Path | None,
        url_override: str | None,
        strict_network: bool,
        options: dict[str, Any] | None = None,
    ) -> Extracted:
        options = dict(options or {})
        max_files = options.get("max_files")
        max_records = options.get("max_records")
        variant_filter = str(options.get("variant") or "").strip().lower()

        records: list[dict[str, Any]] = []
        content_type = None

        if from_file:
            paths: list[Path]
            if from_file.is_dir():
                paths = sorted([p for p in from_file.glob("*.json") if p.is_file()])
                note = "from-dir"
            else:
                paths = [from_file]
                note = "from-file"

            for p in paths:
                try:
                    items = json.loads(p.read_bytes())
                except Exception as exc:  # noqa: BLE001
                    if strict_network:
                        raise
                    continue
                if not isinstance(items, list):
                    continue

                for item in items:
                    if not isinstance(item, dict):
                        continue
                    records.append(
                        {
                            "list_url": f"file://{p.resolve()}",
                            "variant": p.name.split("__", 1)[0],
                            "payload": item,
                        }
                    )

            if isinstance(max_records, int) and max_records > 0:
                records = records[:max_records]

            meta = {
                "source": "congreso_intervenciones_from_file",
                "paths": [str(p) for p in paths],
                "records": len(records),
            }
            payload_bytes = stable_json(meta).encode("utf-8")
            raw_path = raw_output_path(raw_dir, self.source_id, "json")
            raw_path.write_bytes(payload_bytes)
            return Extracted(
                source_id=self.source_id,
                source_url=f"file://{from_file.resolve()}",
                resolved_url=f"file://{from_file.resolve()}",
                fetched_at=now_utc_iso(),
                raw_path=raw_path,
                content_sha256=sha256_bytes(payload_bytes),
                content_type=None,
                bytes=len(payload_bytes),
                note=note,
                payload=payload_bytes,
                records=records,
            )

        resolved_url = self.resolve_url(url_override, timeout)
        html_bytes, content_type = http_get_bytes(
            resolved_url,
            timeout,
            headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
        )
        html = html_bytes.decode("utf-8", errors="replace")

        hrefs = [m.group("href") for m in INTERVENCIONES_JSON_RE.finditer(html)]
        urls: list[str] = []
        seen: set[str] = set()
        for href in hrefs:
            u = urljoin(CONGRESO_BASE, href)
            if u in seen:
                continue
            seen.add(u)
            urls.append(u)

        # Prefer the "Iniciativa" export by default (it contains NUMEXPEDIENTE, etc),
        # but allow overriding via options.variant.
        if variant_filter:
            urls = [u for u in urls if variant_filter in _parse_variant_from_url(u).lower()]
        else:
            iniciativa = [u for u in urls if "intervencionesiniciativa" in _parse_variant_from_url(u).lower()]
            if iniciativa:
                urls = iniciativa

        if isinstance(max_files, int) and max_files > 0:
            urls = urls[:max_files]

        failures: list[str] = []
        downloaded: list[dict[str, Any]] = []
        for url in urls:
            try:
                payload_bytes, ct = http_get_bytes(url, timeout, headers={"Accept": "application/json"})
                if ct and "json" not in ct.lower():
                    raise RuntimeError(f"content_type inesperado: {ct}")
                items = json.loads(payload_bytes)
                if not isinstance(items, list):
                    raise RuntimeError("payload inesperado: no es lista")
                variant = _parse_variant_from_url(url)
                downloaded.append({"url": url, "variant": variant, "items": len(items)})
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    records.append({"list_url": url, "variant": variant, "payload": item})
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{url} -> {type(exc).__name__}: {exc}")
                if strict_network:
                    raise

        if isinstance(max_records, int) and max_records > 0:
            records = records[:max_records]

        meta = {
            "source": "congreso_intervenciones_catalog",
            "list_url": resolved_url,
            "json_urls_total": len(urls),
            "downloaded": downloaded,
            "records": len(records),
            "failures": failures,
        }
        meta_bytes = stable_json(meta).encode("utf-8")
        raw_path = raw_output_path(raw_dir, self.source_id, "json")
        raw_path.write_bytes(meta_bytes)

        note = "network"
        if failures:
            note = "network-partial"

        return Extracted(
            source_id=self.source_id,
            source_url=resolved_url,
            resolved_url=resolved_url,
            fetched_at=now_utc_iso(),
            raw_path=raw_path,
            content_sha256=sha256_bytes(meta_bytes),
            content_type=content_type,
            bytes=len(meta_bytes),
            note=note,
            payload=meta_bytes,
            records=records,
        )

