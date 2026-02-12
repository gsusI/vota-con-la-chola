from __future__ import annotations

import html as htmlmod
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from etl.politicos_es.util import normalize_ws, now_utc_iso, sha256_bytes, stable_json

from ..config import SOURCE_CONFIG
from ..http import http_get_bytes
from ..raw import raw_output_path
from ..types import Extracted
from .base import BaseConnector


SENADO_BASE = "https://videoservlet.senado.es"


def _extract_legislature(url: str) -> str | None:
    try:
        qs = parse_qs(urlparse(url).query)
        vals = qs.get("legis") or []
        if vals:
            return normalize_ws(vals[0]) or None
    except Exception:  # noqa: BLE001
        return None
    return None


def _parse_vote_ids_from_url(url: str | None) -> tuple[int | None, int | None]:
    if not url:
        return None, None
    try:
        qs = parse_qs(urlparse(url).query)
        id1 = qs.get("id1", [None])[0]
        id2 = qs.get("id2", [None])[0]
        return int(id1) if id1 and str(id1).isdigit() else None, int(id2) if id2 and str(id2).isdigit() else None
    except Exception:  # noqa: BLE001
        return None, None


def _records_from_tipo12_xml(payload: bytes, source_url: str) -> list[dict[str, Any]]:
    root = ET.fromstring(payload)
    if root.tag != "iniciativaVotaciones":
        raise RuntimeError(f"XML inesperado para Senado votaciones: root={root.tag!r}")

    leg = _extract_legislature(source_url)
    tipo_ex = normalize_ws(root.findtext("tipoExpediente"))
    num_ex = normalize_ws(root.findtext("numeroExpediente"))
    iniciativa_title = normalize_ws(root.findtext("titulo"))
    iniciativa_url_raw = normalize_ws(root.findtext("urlPagina"))
    iniciativa_url = urljoin(SENADO_BASE, iniciativa_url_raw) if iniciativa_url_raw else None

    records: list[dict[str, Any]] = []
    for v in root.findall("./votaciones/votacion"):
        vote_title = normalize_ws(v.findtext("tituloVotacion"))
        vote_url_raw = normalize_ws(v.findtext("urlVotacion"))
        vote_url = urljoin(SENADO_BASE, vote_url_raw) if vote_url_raw else None
        fich = v.find("fichGenVotacion")
        vote_file_url = None
        vote_file_format = None
        if fich is not None:
            vote_file_url = normalize_ws(fich.findtext("fichUrlVotacion")) or None
            vote_file_format = normalize_ws(fich.findtext("fichFormatoVotacion")) or None

        session_id, vote_id = _parse_vote_ids_from_url(vote_url)
        record_payload = {
            "legislature": leg,
            "tipo_expediente": tipo_ex,
            "numero_expediente": num_ex,
            "iniciativa_title": iniciativa_title,
            "iniciativa_url": iniciativa_url,
            "vote_title": vote_title,
            "vote_url": vote_url,
            "vote_file_url": vote_file_url,
            "vote_file_format": vote_file_format,
            "session_id": session_id,
            "vote_id": vote_id,
            "source_tipo12_url": source_url,
        }
        records.append(
            {
                "detail_url": source_url,
                "legislature": leg,
                "payload": record_payload,
            }
        )
    return records


class SenadoVotacionesConnector(BaseConnector):
    source_id = "senado_votaciones"

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
        max_votes = options.get("max_votes")
        content_type = None
        records: list[dict[str, Any]] = []

        if from_file:
            paths: list[Path]
            if from_file.is_dir():
                paths = sorted([p for p in from_file.glob("*.xml") if p.is_file()])
                note = "from-dir"
            else:
                paths = [from_file]
                note = "from-file"

            for p in paths:
                xml_bytes = p.read_bytes()
                records.extend(_records_from_tipo12_xml(xml_bytes, f"file://{p.resolve()}"))
            if isinstance(max_votes, int) and max_votes > 0:
                records = records[:max_votes]

            meta = {
                "source": "senado_votaciones_from_file",
                "paths": [str(p) for p in paths],
                "vote_records": len(records),
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
        html_text = html_bytes.decode("utf-8", errors="replace")

        hrefs = re.findall(r'href="([^"]*tipoFich=12[^"]*)"', html_text, flags=re.I)
        tipo12_urls: list[str] = []
        seen: set[str] = set()
        for href in hrefs:
            clean = htmlmod.unescape(href)
            clean = re.sub(r";jsessionid=[^?]+", "", clean, flags=re.I)
            url = urljoin(SENADO_BASE, clean)
            if url in seen:
                continue
            seen.add(url)
            tipo12_urls.append(url)

        failures: list[str] = []
        for u in tipo12_urls:
            if isinstance(max_votes, int) and max_votes > 0 and len(records) >= max_votes:
                break
            try:
                xml_bytes, ct = http_get_bytes(u, timeout, headers={"Accept": "application/xml,text/xml,*/*"})
                if ct and "xml" not in ct.lower():
                    raise RuntimeError(f"content_type inesperado: {ct}")
                rows = _records_from_tipo12_xml(xml_bytes, u)
                if isinstance(max_votes, int) and max_votes > 0:
                    remaining = max_votes - len(records)
                    if remaining <= 0:
                        break
                    records.extend(rows[:remaining])
                else:
                    records.extend(rows)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{u} -> {type(exc).__name__}: {exc}")
                if strict_network:
                    raise

        meta = {
            "source": "senado_votaciones_catalog",
            "list_url": resolved_url,
            "tipo12_urls_total": len(tipo12_urls),
            "vote_records": len(records),
            "failures": failures,
        }
        payload_bytes = stable_json(meta).encode("utf-8")
        raw_path = raw_output_path(raw_dir, self.source_id, "json")
        raw_path.write_bytes(payload_bytes)

        note = "network"
        if failures:
            note = "network-partial"

        return Extracted(
            source_id=self.source_id,
            source_url=resolved_url,
            resolved_url=resolved_url,
            fetched_at=now_utc_iso(),
            raw_path=raw_path,
            content_sha256=sha256_bytes(payload_bytes),
            content_type=content_type,
            bytes=len(payload_bytes),
            note=note,
            payload=payload_bytes,
            records=records,
        )
